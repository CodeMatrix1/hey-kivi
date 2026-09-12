"""Thin Hindsight client adapter for durable Fact/Preference/Episode storage."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re
from typing import Any, Callable, TypeVar

from hindsight_pipeline_2.kivi.config import RETAIN_MISSION, Settings

logger = logging.getLogger(__name__)

_T = TypeVar("_T")
# Hindsight's client keeps a shared aiohttp session bound to one event loop.
# FastAPI /chat runs in a threadpool where the default loop breaks aiohttp timeouts.
# Route all Hindsight I/O through a single worker thread with a persistent loop.
_HINDSIGHT_EXEC = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="hindsight-sync"
)


def _hindsight_worker_loop() -> asyncio.AbstractEventLoop:
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def _run_hindsight(fn: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
    """Run a Hindsight client call on the dedicated hindsight worker thread."""

    def _worker() -> _T:
        if asyncio.iscoroutinefunction(fn):
            loop = _hindsight_worker_loop()
            return loop.run_until_complete(fn(*args, **kwargs))
        return fn(*args, **kwargs)

    return _HINDSIGHT_EXEC.submit(_worker).result()


class HindsightBackend:
    backend_name: str = "hindsight"

    def __init__(self, settings: Settings | None = None, client: Any | None = None):
        self.settings = settings or Settings.from_env()
        if client is not None:
            self._client = client
        else:
            from hindsight_client import Hindsight

            kwargs: dict[str, Any] = {"base_url": self.settings.hindsight_base_url}
            if self.settings.hindsight_api_key:
                kwargs["api_key"] = self.settings.hindsight_api_key
            self._client = Hindsight(**kwargs)

    def bank_id(self, user_id: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id.strip()) or "user"
        return f"{self.settings.bank_prefix}_{safe}"

    def ensure_bank(self, user_id: str) -> str:
        bank_id = self.bank_id(user_id)
        create = getattr(self._client, "create_bank", None)
        if callable(create):
            try:
                create(bank_id=bank_id, name=f"Kivi2 ({user_id})", mission=RETAIN_MISSION)
            except Exception as exc:  # noqa: BLE001
                logger.debug("create_bank skipped: %s", exc)
        update = getattr(self._client, "update_bank_config", None)
        if callable(update):
            try:
                update(bank_id, retain_mission=RETAIN_MISSION, retain_extraction_mode="concise")
            except Exception:  # noqa: BLE001
                try:
                    update(
                        bank_id=bank_id,
                        retain_mission=RETAIN_MISSION,
                        retain_extraction_mode="concise",
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("update_bank_config skipped: %s", exc)
        return bank_id

    def retain(self, user_id: str, content: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        bank_id = self.ensure_bank(user_id)
        meta = metadata or {}
        retain_kwargs: dict[str, Any] = {
            "bank_id": bank_id,
            "content": content,
            "context": "Kivi durable semantic memory",
            "retain_async": False,
        }
        if meta:
            retain_kwargs["metadata"] = meta
        try:
            resp = _run_hindsight(self._client.aretain, **retain_kwargs)
        except TypeError:
            retain_kwargs.pop("metadata", None)
            try:
                resp = _run_hindsight(self._client.aretain, **retain_kwargs)
            except TypeError:
                resp = _run_hindsight(self._client.aretain, bank_id=bank_id, content=content)
        return {"bank_id": bank_id, "response": resp, "metadata": meta}

    def recall(self, user_id: str, query: str, *, limit: int = 12) -> list[dict[str, Any]]:
        bank_id = self.ensure_bank(user_id)
        try:
            response = _run_hindsight(
                self._client.arecall,
                bank_id=bank_id,
                query=query,
                budget=self.settings.recall_budget,
            )
        except TypeError:
            response = _run_hindsight(self._client.arecall, bank_id=bank_id, query=query)
        results = getattr(response, "results", None)
        if results is None and isinstance(response, dict):
            results = response.get("results", [])
        if results is None:
            results = list(response) if isinstance(response, list) else []
        out: list[dict[str, Any]] = []
        for item in results[:limit]:
            if isinstance(item, dict):
                text = item.get("text") or item.get("memory") or item.get("content") or ""
                mid = item.get("id") or item.get("memory_id")
                metadata = item.get("metadata") or {}
            else:
                text = getattr(item, "text", None) or getattr(item, "memory", "") or ""
                mid = getattr(item, "id", None)
                metadata = getattr(item, "metadata", None) or {}
            if not text:
                continue
            if "status=superseded" in text:
                continue
            out.append(
                {
                    "id": str(mid or f"anon_{abs(hash(text))}"),
                    "text": str(text),
                    "metadata": metadata if isinstance(metadata, dict) else {},
                    "raw": item,
                }
            )
        return out

    def list_memories(self, user_id: str) -> list[dict[str, Any]]:
        return self.recall(user_id, "facts preferences episodes names projects", limit=50)

    def count_memories(self, user_id: str) -> int | None:
        """Total memory units in the Hindsight bank (not corpus_ingestions row count)."""
        bank_id = self.ensure_bank(user_id)
        try:
            response = _run_hindsight(self._client.list_memories, bank_id, limit=1, offset=0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("count_memories failed: %s", exc)
            return None
        total = getattr(response, "total", None)
        if total is None and isinstance(response, dict):
            total = response.get("total")
        return int(total) if total is not None else None

    def reset(self, user_id: str) -> dict[str, Any]:
        bank_id = self.bank_id(user_id)
        for name in ("clear_memories", "delete_bank"):
            fn = getattr(self._client, name, None)
            if not callable(fn):
                continue
            try:
                detail = fn(bank_id)
                return {"bank_id": bank_id, "cleared": True, "detail": detail}
            except TypeError:
                try:
                    detail = fn(bank_id=bank_id)
                    return {"bank_id": bank_id, "cleared": True, "detail": detail}
                except Exception as exc:  # noqa: BLE001
                    logger.debug("%s failed: %s", name, exc)
            except Exception as exc:  # noqa: BLE001
                logger.debug("%s failed: %s", name, exc)
        raise RuntimeError(f"Unable to reset bank {bank_id}")

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()


def get_memory_backend(settings: Settings | None = None) -> Any:
    """Return memory backend. Only Hindsight backend is supported."""
    cfg = settings or Settings.from_env()
    if cfg.memory_backend == "hindsight":
        return HindsightBackend(cfg)
    raise ValueError(
        f"Unsupported memory backend: {cfg.memory_backend}. Only 'hindsight' is supported."
    )



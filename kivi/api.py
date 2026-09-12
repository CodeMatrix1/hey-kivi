"""Hey Kivi Phase 1 API — chatbot + inspectable decision traces."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.staticfiles import StaticFiles

UI_ASSET_VERSION = "35"


class _NoCacheStaticFiles(StaticFiles):
    """Serve chat UI assets without long-lived browser cache (dev inspectability)."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        response = await super().get_response(path, scope)
        if path.endswith((".js", ".css", ".html")):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

from hindsight_pipeline_2.kivi.agent import HeyKiviAgent
from hindsight_pipeline_2.kivi.config import Settings
from hindsight_pipeline_2.kivi.corpus.import_corpus import ingest_jsonl, ingest_record
from hindsight_pipeline_2.kivi.models import DictationRecord, utc_now_iso
from hindsight_pipeline_2.paths import DATA_CORPUS_DIR, WEB_DIR
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.memory.hindsight_adapter import get_memory_backend
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.instrumentation import (
    MetricsTimer,
    build_turn_metrics,
    sqlite_counts,
)
from hindsight_pipeline_2.kivi.seed import seed_demo

STATIC_DIR = WEB_DIR
CORPUS_DATA_DIR = DATA_CORPUS_DIR

settings = Settings.from_env()
store = DictationStore(settings.db_path)
lexical_store = LexicalStore(settings.db_path)
memory = get_memory_backend(settings)
# Default: use LLM when keys exist. Set KIVI_REQUIRE_LLM=false for offline/rules-only.
_require_llm = os.getenv("KIVI_REQUIRE_LLM", "true").strip().lower() in {
    "1",
    "true",
    "yes",
}
agent = HeyKiviAgent(
    settings=settings,
    store=store,
    lexical_store=lexical_store,
    memory_backend=memory,
    require_llm=_require_llm,
)

app = FastAPI(title="Hey Kivi", version="0.2.0")
if STATIC_DIR.is_dir():
    app.mount("/static", _NoCacheStaticFiles(directory=str(STATIC_DIR)), name="static")


class ContextMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    user_id: str = Field(default=settings.default_user_id, min_length=1, max_length=128)
    context_messages: list[ContextMessage] | None = Field(default=None, max_length=6)


class SeedRequest(BaseModel):
    user_id: str = Field(default=settings.default_user_id, min_length=1, max_length=128)


class CorpusImportRequest(BaseModel):
    user_id: str = Field(default=settings.default_user_id, min_length=1, max_length=128)
    path: str = Field(
        default="smoke.jsonl",
        min_length=1,
        max_length=512,
        description="JSONL filename under data/corpus/ or an absolute path",
    )


@app.get("/")
def root() -> FileResponse:
    index = STATIC_DIR / "dist" / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(
        404,
        "chat UI missing — run: cd web/kivi-ui && npm install && npm run build",
    )


@app.get("/health")
def health() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "memory_backend": settings.memory_backend,
        "hindsight_base_url": settings.hindsight_base_url
        if settings.memory_backend == "hindsight"
        else None,
        "require_llm": _require_llm,
        "llm_loaded": agent.json_llm is not None,
        "llm_provider": settings.llm_provider,
        "db_path": str(settings.db_path),
        "ui_asset_version": UI_ASSET_VERSION,
        "kivi_chat": agent.kivi_chat,
        "default_user_id": settings.default_user_id,
    }
    if settings.default_user_name:
        payload["default_user_name"] = settings.default_user_name
    return payload


@app.post("/chat")
def chat_endpoint(body: ChatRequest) -> dict[str, Any]:
    user_id = body.user_id.strip()
    message = body.message.strip()
    db_before = sqlite_counts(settings.db_path, user_id)
    timer = MetricsTimer()
    context_messages = None
    if body.context_messages:
        context_messages = [
            {"role": m.role, "content": m.content.strip()} for m in body.context_messages
        ]
    result = agent.chat(user_id, message, context_messages=context_messages)
    payload = result.to_dict()
    payload["metrics"] = build_turn_metrics(
        trace=payload["trace"],
        db_before=db_before,
        db_after=sqlite_counts(settings.db_path, user_id),
        elapsed_ms=timer.elapsed_ms(),
    )
    return payload


@app.post("/seed")
def seed_endpoint(body: SeedRequest | None = None) -> dict[str, Any]:
    user_id = (body.user_id if body else settings.default_user_id).strip()
    return seed_demo(user_id, settings=settings)


@app.post("/corpus/import")
def corpus_import_endpoint(body: CorpusImportRequest) -> dict[str, Any]:
    """JSONL → DictationStore → lexical canonicalize → Hindsight retain (same as CLI)."""
    user_id = body.user_id.strip()
    raw_path = Path(body.path.strip())
    if raw_path.is_absolute():
        path = raw_path
    else:
        # Only allow files under data/corpus/ (no path escape).
        candidate = (CORPUS_DATA_DIR / raw_path.name).resolve()
        if not str(candidate).startswith(str(CORPUS_DATA_DIR.resolve())):
            raise HTTPException(400, "path must resolve under data/corpus/")
        path = candidate
    if not path.is_file():
        raise HTTPException(404, f"corpus file not found: {path}")
    try:
        return ingest_jsonl(
            path,
            user_id=user_id,
            store=store,
            lexical_store=lexical_store,
            memory=memory,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


def _hindsight_memory_count(user_id: str) -> int | None:
    count_fn = getattr(memory, "count_memories", None)
    if not callable(count_fn):
        return None
    return count_fn(user_id)


@app.get("/stats/{user_id}")
def user_stats(user_id: str) -> dict[str, Any]:
    """Lightweight counts — dictations from SQLite; memories from Hindsight bank total."""
    counts = sqlite_counts(settings.db_path, user_id)
    return {
        "user_id": user_id,
        "dictations": counts["dictations"],
        "corpus_ingestions": counts["corpus_ingestions"],
        "hindsight_memories": _hindsight_memory_count(user_id),
        "lexical_mappings": counts["lexical_mappings"],
        "interactions": counts.get("interactions", 0),
    }


@app.get("/memories/{user_id}")
def list_memories(user_id: str, sample_limit: int = 20) -> dict[str, Any]:
    """count = Hindsight bank total; memories = recall sample (not full bank)."""
    cap = max(1, min(sample_limit, 50))
    items = memory.list_memories(user_id)[:cap]
    return {
        "user_id": user_id,
        "count": _hindsight_memory_count(user_id),
        "corpus_ingestions": sqlite_counts(settings.db_path, user_id)["corpus_ingestions"],
        "sample_count": len(items),
        "memories": items,
    }


class CreateTextDictationRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)


@app.post("/dictations/{user_id}")
def create_text_dictation(user_id: str, body: CreateTextDictationRequest) -> dict[str, Any]:
    """Add a text note to history (not speech) — full dictation ingest + Hindsight retain."""
    uid = user_id.strip()
    text = body.text.strip()
    record = DictationRecord(
        id=f"d_note_{uuid4().hex[:12]}",
        user_id=uid,
        asr=text,
        formatted=text,
        created_at=utc_now_iso(),
    )
    try:
        return ingest_record(
            record,
            store=store,
            lexical_store=lexical_store,
            memory=memory,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/dictations/{user_id}")
def list_dictations(user_id: str, limit: int = 20) -> dict[str, Any]:
    total = store.count_for_user(user_id)
    cap = max(1, min(limit, 500))
    rows = store.list_for_user(user_id, limit=cap)
    return {
        "user_id": user_id,
        "count": total,
        "returned": len(rows),
        "dictations": [r.model_dump() for r in rows],
    }


@app.get("/lexical/{user_id}")
def list_lexical(user_id: str) -> dict[str, Any]:
    rows = lexical_store.list_active(user_id)
    return {
        "user_id": user_id,
        "count": len(rows),
        "mappings": [r.to_dict() for r in rows],
    }


class LexicalPreferenceRequest(BaseModel):
    preferred: str = Field(..., min_length=1, max_length=200)
    inputs: list[str] = Field(..., min_length=1, max_length=20)
    previous_preferred: str | None = Field(default=None, max_length=200)


@app.post("/lexical/{user_id}/preference")
def save_lexical_preference(user_id: str, body: LexicalPreferenceRequest) -> dict[str, Any]:
    uid = user_id.strip()
    preferred = body.preferred.strip()
    try:
        lexical_store.replace_preference_group(
            uid,
            preferred,
            body.inputs,
            previous_preferred=body.previous_preferred,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    rows = lexical_store.list_active(uid)
    mappings = [r.to_dict() for r in rows if r.canonical == preferred]
    return {"ok": True, "preferred": preferred, "mappings": mappings}


def main() -> None:
    import uvicorn

    port = int(os.getenv("KIVI_API_PORT", "8002"))
    uvicorn.run(
        "hindsight_pipeline_2.kivi.api:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()

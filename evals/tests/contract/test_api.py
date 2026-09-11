"""Contract tests — FastAPI HTTP surface and response shape.

Tier: contract (TestClient + patched stub agent; no Docker)

Tests:
- test_health_returns_default_user — ``GET /health`` returns ok, memory_backend, save_chats, ui_asset_version, default_user_id/name
- test_chat_response_contract — ``POST /chat`` returns reply, trace, and metrics (elapsed_ms, db_delta, llm/retain counts)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hindsight_pipeline_2.kivi.agent import HeyKiviAgent
from hindsight_pipeline_2.kivi.config import Settings
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.lexical.lexical_extract import scripted_lexical_llm
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.memory.stub_memory import StubMemory


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import hindsight_pipeline_2.kivi.api as api_module

    monkeypatch.setenv("KIVI_SAVE_CHATS", "true")
    db = tmp_path / "api.sqlite3"
    settings = Settings(
        hindsight_base_url="http://localhost:8888",
        hindsight_api_key=None,
        bank_prefix="kivi2api",
        memory_backend="hindsight",
        llm_provider="groq",
        db_path=db,
        recall_budget="mid",
        default_user_id="api_test_user",
        default_user_name="API Test User",
    )
    store = DictationStore(db)
    lexical_store = LexicalStore(db)
    memory = StubMemory()
    agent = HeyKiviAgent(
        settings=settings,
        store=store,
        lexical_store=lexical_store,
        memory_backend=memory,
        require_llm=False,
        json_llm=None,
        text_llm=None,
        lexical_llm=scripted_lexical_llm({"mappings": []}),
    )
    monkeypatch.setattr(api_module, "settings", settings)
    monkeypatch.setattr(api_module, "store", store)
    monkeypatch.setattr(api_module, "lexical_store", lexical_store)
    monkeypatch.setattr(api_module, "memory", memory)
    monkeypatch.setattr(api_module, "agent", agent)
    monkeypatch.setattr(api_module, "_require_llm", False)
    client = TestClient(api_module.app)
    yield client, agent
    agent.close()


def test_health_returns_default_user(api_client):
    client, _ = api_client
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["memory_backend"] == "hindsight"
    assert data["save_chats"] is True
    assert data["ui_asset_version"]
    assert data["default_user_id"] == "api_test_user"
    assert data["default_user_name"] == "API Test User"


def test_chat_response_contract(api_client):
    client, _ = api_client
    response = client.post(
        "/chat",
        json={"message": "hello there", "user_id": "api_test_user"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "trace" in data
    assert "metrics" in data
    metrics = data["metrics"]
    assert "elapsed_ms" in metrics
    assert "db_delta" in metrics
    assert "llm_call_count" in metrics
    assert "retain_call_count" in metrics
    assert metrics["retain_call_count"] == 1

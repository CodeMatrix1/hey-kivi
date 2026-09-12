"""Contract tests — FastAPI HTTP surface and response shape.

Tier: contract (TestClient + patched stub agent; no Docker)

Tests:
- test_health_returns_default_user — ``GET /health`` returns ok, memory_backend, kivi_chat, ui_asset_version
- test_chat_response_contract — ``POST /chat`` returns reply, trace, and metrics (elapsed_ms, db_delta, llm/retain counts)
- test_chat_cross_recall_skips_retain — recall queries skip semantic retain (``retain_call_count`` 0)
- test_create_text_dictation_retain_uses_dictation_provenance — text notes use ``source_dictation_id``, not ``kivi_chat``
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

    monkeypatch.setenv("KIVI_CHAT", "true")
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
    assert data["kivi_chat"] is True
    assert data["ui_asset_version"]
    assert data["default_user_id"] == "api_test_user"
    assert data["default_user_name"] == "API Test User"


def test_chat_accepts_context_messages(api_client):
    client, _ = api_client
    response = client.post(
        "/chat",
        json={
            "message": "follow up",
            "user_id": "api_test_user",
            "context_messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "trace" in data


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


def test_chat_cross_recall_skips_retain(api_client):
    client, agent = api_client
    user_id = "api_test_user"
    before = len(agent.memory.list_memories(user_id))
    response = client.post(
        "/chat",
        json={
            "message": "What have I been working on for the Kivi meeting?",
            "user_id": user_id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["trace"]["wants_cross_recall"] is True
    assert data["trace"]["semantic_retain"] is False
    assert data["metrics"]["retain_call_count"] == 0
    assert len(agent.memory.list_memories(user_id)) == before


def test_create_text_dictation(api_client):
    client, _ = api_client
    user_id = "api_test_user"
    response = client.post(
        f"/dictations/{user_id}",
        json={"text": "Payments team sync moved to Thursday."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in {"imported", "replaced", "skipped"}
    assert data["id"].startswith("d_note_")
    listed = client.get(f"/dictations/{user_id}?limit=500")
    assert listed.status_code == 200
    ids = {d["id"] for d in listed.json()["dictations"]}
    assert data["id"] in ids


def test_create_text_dictation_retain_uses_dictation_provenance(api_client):
    client, agent = api_client
    user_id = "api_test_user"
    before = len(agent.memory.list_memories(user_id))
    response = client.post(
        f"/dictations/{user_id}",
        json={"text": "Quarterly planning notes for infra."},
    )
    assert response.status_code == 200
    note_id = response.json()["id"]
    assert note_id.startswith("d_note_")
    memories = agent.memory.list_memories(user_id)
    assert len(memories) > before
    latest = memories[-1]
    text = str(latest.get("text") or "")
    meta = latest.get("metadata") or {}
    assert "kivi_chat=true" not in text.lower()
    assert meta.get("kivi_chat") is not True
    assert f"source_dictation_id={note_id}" in text


def test_lexical_preference_endpoint(api_client):
    client, _ = api_client
    user_id = "api_test_user"
    response = client.post(
        f"/lexical/{user_id}/preference",
        json={
            "preferred": "petrol bunk",
            "inputs": ["gas station", "petrol pump"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["preferred"] == "petrol bunk"
    mappings = data["mappings"]
    assert len(mappings) == 2
    canonicals = {m["canonical"] for m in mappings}
    aliases = {m["alias"] for m in mappings}
    assert canonicals == {"petrol bunk"}
    assert aliases == {"gas station", "petrol pump"}

    rename = client.post(
        f"/lexical/{user_id}/preference",
        json={
            "preferred": "fuel bunk",
            "inputs": ["gas station"],
            "previous_preferred": "petrol bunk",
        },
    )
    assert rename.status_code == 200
    renamed = rename.json()["mappings"]
    assert all(m["canonical"] == "fuel bunk" for m in renamed)
    assert len(renamed) == 1

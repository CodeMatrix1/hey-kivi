"""Shared pytest fixtures for all eval tiers (unit, agent, corpus, contract, scenario).

Provides: stub_memory, eval_settings, eval_harness, agent, no_save_agent, store.
Subpackages under ``evals/tests/`` inherit these fixtures automatically.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hindsight_pipeline_2.kivi.agent import HeyKiviAgent
from hindsight_pipeline_2.kivi.config import Settings
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.lexical.lexical_extract import scripted_lexical_llm
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.models import EpisodeMemory, FactMemory
from hindsight_pipeline_2.kivi.seed import seed_demo
from hindsight_pipeline_2.kivi.memory.stub_memory import StubMemory, retain_typed


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: requires Docker Hindsight + API keys")


@pytest.fixture()
def stub_memory() -> StubMemory:
    return StubMemory()


@pytest.fixture(autouse=True)
def _enable_kivi_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIVI_CHAT", "true")


@pytest.fixture()
def eval_settings(tmp_path: Path) -> Settings:
    return Settings(
        hindsight_base_url="http://localhost:8888",
        hindsight_api_key=None,
        bank_prefix="kivi2test",
        memory_backend="hindsight",
        llm_provider="groq",
        db_path=tmp_path / "test.sqlite3",
        recall_budget="mid",
        default_user_id="golden_goose_eval_user",
        default_user_name=None,
    )


@pytest.fixture()
def eval_harness(eval_settings: Settings, stub_memory: StubMemory):
    store = DictationStore(eval_settings.db_path)
    lex = LexicalStore(eval_settings.db_path)
    return {
        "settings": eval_settings,
        "store": store,
        "lex": lex,
        "memory": stub_memory,
    }


@pytest.fixture()
def store(tmp_path: Path) -> DictationStore:
    return DictationStore(tmp_path / "find.sqlite3")


def _seed_agent_memories(memory: StubMemory, user_id: str) -> None:
    for mem in (
        FactMemory(
            id="f_backend_auth",
            text="Backend auth refactor for next week's product sync.",
            subject="user",
            predicate="works_on",
            object="backend auth refactor",
            source="seed",
            user_id=user_id,
        ),
        EpisodeMemory(
            id="e_rate_limits",
            text="Slack dump about API rate limits with Aaditya.",
            approx_time="2026-09-04T17:03:00+00:00",
            related_dictation_id="d_slack_1700",
            source="seed",
            user_id=user_id,
        ),
        FactMemory(
            id="f_maya",
            text=(
                "[source_dictation_id=d_corpus_maya created_at=2026-09-02T10:00:00+00:00 "
                f"user_id={user_id}]\nMaya lives in Pune."
            ),
            subject="Maya",
            predicate="lives_in",
            object="Pune",
            source="seed",
            user_id=user_id,
        ),
    ):
        retain_typed(memory, user_id, mem)


@pytest.fixture()
def agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KIVI_CHAT", "true")
    db = tmp_path / "kivi.sqlite3"
    settings = Settings(
        hindsight_base_url="http://localhost:8888",
        hindsight_api_key=None,
        bank_prefix="kivi2test",
        memory_backend="hindsight",
        llm_provider="groq",
        db_path=db,
        recall_budget="mid",
        default_user_id="golden_goose_eval_user",
    )
    store = DictationStore(db)
    lex = LexicalStore(db)
    memory = StubMemory()
    a = HeyKiviAgent(
        settings=settings,
        store=store,
        lexical_store=lex,
        memory_backend=memory,
        require_llm=False,
        json_llm=None,
        text_llm=None,
        lexical_llm=scripted_lexical_llm({"mappings": []}),
    )
    seed_demo("demo_user", settings=settings)
    _seed_agent_memories(memory, "demo_user")
    yield a
    a.close()


@pytest.fixture()
def no_save_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KIVI_CHAT", "false")
    db = tmp_path / "nosave.sqlite3"
    settings = Settings(
        hindsight_base_url="http://localhost:8888",
        hindsight_api_key=None,
        bank_prefix="kivi2nosave",
        memory_backend="hindsight",
        llm_provider="groq",
        db_path=db,
        recall_budget="mid",
    )
    memory = StubMemory()
    agent = HeyKiviAgent(
        settings=settings,
        store=DictationStore(db),
        lexical_store=LexicalStore(db),
        memory_backend=memory,
        require_llm=False,
        json_llm=None,
        text_llm=None,
        lexical_llm=scripted_lexical_llm({"mappings": []}),
    )
    yield agent
    agent.close()

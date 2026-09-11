"""Bootstrap SQLite lexical mappings from corpus teaching rows."""

from __future__ import annotations

from hindsight_pipeline_2.kivi.corpus.lexical_from_corpus import mapping_from_corpus_record
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore

_bootstrapped_users: set[str] = set()


def ensure_corpus_lexical_bootstrapped(
    user_id: str,
    *,
    store: DictationStore,
    lexical_store: LexicalStore,
) -> int:
    """Upsert mappings from ``lexical_*`` dictations when the user has none yet."""
    if user_id in _bootstrapped_users:
        return 0
    added = 0
    if lexical_store.active_count(user_id) == 0:
        for record in store.list_by_id_prefix(user_id, "lexical_"):
            mapping = mapping_from_corpus_record(record)
            if mapping is None:
                continue
            lexical_store.upsert_mapping(user_id, mapping, source_interaction_id=record.id)
            added += 1
    _bootstrapped_users.add(user_id)
    return added

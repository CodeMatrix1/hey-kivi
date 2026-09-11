# Turn capabilities

One module per chat-turn capability. `HeyKiviAgent.chat()` in `../agent.py`
only orchestrates these steps in order.

| Module | Responsibility |
|--------|----------------|
| `trace_utils.py` | Shared decision-trace helpers (LLM call log, memory cards). |
| `lexical_learn.py` | Extract → validate → upsert mappings; canonicalize message. |
| `semantic_retain.py` | Send canonical text to Hindsight retain. |
| `interpret.py` | Route flags: `wants_dictation` / `wants_cross_recall`. |
| `cross_recall.py` | Hindsight recall + synthesize answer. |
| `dictation.py` | Find dictation candidates; polish when confident. |
| `general_chat.py` | Normal LLM reply when both interpret flags are false. |

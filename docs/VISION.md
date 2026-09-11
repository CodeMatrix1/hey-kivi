# Vision

## What Hey Kivi is

Hey Kivi is a single chat interface that routes each turn to the right capability: cross-recall over semantic memories, find and polish past dictations, lexical learning for explicit spelling and naming preferences, or general chat when no retrieval is needed. There is no separate “dictation mode” in Phase 1 — live speech-to-text dictation is out of scope; the 500-record corpus replays ASR plus formatted transcripts for evaluation.

## How routing works

The interpreter sets `wants_dictation` when you ask to find, open, or polish a specific past artifact (“Find my note about train seats and polish it”). It sets `wants_cross_recall` when answering requires your prior context (“What have I said about travel?” or “Pull together what I already said about the payments review”). Both can be true in one turn. Greetings, teaching a spelling (“It’s Aaditya, not Aditya”), and general knowledge questions stay on the general or lexical path without forced retrieval.

## Memory layers

**Formatted** is the written transcript — what the product treats as what you meant on the page. **ASR** is the raw speech-like text, preserved for audit and search but never rewritten in SQLite. **Lexical mappings** are explicit user rules (alias → canonical) stored in SQLite and applied to formatted text before retain and polish. **Hindsight memories** are durable facts, preferences, and episodes extracted from canonical text on retain.

Formatted is the transcript; lexical is the user’s explicit spelling and name preferences applied on top before memory.

## User control

You can see why Kivi decided via the Developer trace on every response. Kivi abstains when find or cross-recall lacks support rather than inventing facts. You teach spelling and aliases in chat; those become lexical mappings. There is no in-app “forget this memory” button in Phase 1 — engineers reset via `docker compose down -v` or re-import after clearing a user. Correcting a wrong fact is done by stating the correction; a new retain adds updated context rather than editing Hindsight in place.

## Limitations we document honestly

**“In Slack”** or **“around 5 PM”** are conversational hints, not structured filters today. Find uses full-text search plus calendar day, not channel metadata or clock windows (optional hour filters may come later). **Provenance**: parent dictation ids are tracked in SQLite `corpus_ingestions`, not natively inside Hindsight memory cards. **LLM providers**: Hey Kivi’s internal LLM supports Groq or Gemini only (`LLM_PROVIDER`); Hindsight’s container has its own Groq configuration.

## Out of scope for Phase 1

Regular dictation capture, Accept/Reject memory UI, multi-tenant auth, and public hosting. Reviewers restore the included baseline snapshot; full 500-row import is optional reproducibility only.

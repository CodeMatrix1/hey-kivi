# Positioning

## The first question: what is Hey Kivi?

**Hey Kivi is a personal workspace assistant that answers from your own history** — past dictations, retained chat, and explicit spelling preferences — instead of inventing facts. You ask in one chat interface; Kivi routes each turn to semantic recall, note find/polish, lexical learning, or general chat, and shows an inspectable trace for every decision.

It is built for people who already capture thinking in voice notes and messages and need to **retrieve, prepare, and reason** over that material later (meetings, planning, follow-ups) without treating the assistant as a generic Q&A bot.

## Who it is for

- **You, revisiting your notes** — “What did I say about the payments review?” “Find my train-seat preference and polish it for Slack.”
- **Reviewers and engineers** — reproducible corpus, baseline snapshot, offline pytest, and per-turn `DecisionTrace` to verify behaviour.
- **Not** a multi-tenant SaaS, live microphone dictation product, or memory editor with accept/reject UI in this phase.

## What you get

| Capability | What it does |
|------------|----------------|
| **Cross-recall** | Synthesizes answers from Hindsight memories (facts, preferences, episodes). Abstains when support is thin. |
| **Find & polish** | Deterministic FTS5 search over dictation transcripts, then optional LLM polish for one selected note. |
| **Lexical learning** | You teach spellings and aliases in chat (“It’s Aaditya, not Aditya”); Kivi stores mappings and applies them before retain and polish. |
| **Inspectable traces** | Every reply includes routing flags, tools used, memories considered, and abstain vs answer rationale. |
| **Product UI** | Multi-thread chat, history notes, client-side reminders, personalization feed, and developer query library. |

## How it is different

| Generic chatbot | Hey Kivi |
|-----------------|----------|
| One undifferentiated memory blob | **Three layers**: Hindsight (semantic), SQLite dictations (searchable artifacts), lexical mappings (explicit rules) |
| Answers even when unsure | **Abstains** when recall/find lack grounded support |
| Opaque reasoning | **DecisionTrace** on every turn |
| Rewrites your source notes silently | Dictations are **append-only** in SQLite; polish runs on the find path only |
| Assistant output becomes “memory” | **Hard rule**: Kivi never retains its own replies as durable memory |

**Division of labour:** Hindsight stores and retrieves semantic units. Kivi owns interpret routing, relevance, worthiness, lexical reconcile, and when memory changes behaviour.

## Golden Goose submission

This repo is a **self-contained Phase 1** demo: ~500 synthetic transcripts, Path A baseline restore (~5 minutes to review), optional Path B full import for reproducibility, and 100+ offline tests. See [RUN.md](RUN.md) for the reviewer path.

## One-line versions

- **Elevator:** Personal assistant that recalls and prepares from your dictations and chat — with traces, not guesses.
- **Technical:** LangGraph-style agent + Hindsight memory + SQLite FTS + lexical mappings, exposed as FastAPI and a React chat UI.
- **Honest:** Strong on grounded recall and note polish; weak on live ASR, structured channel/time filters, and in-app memory deletion.

More detail: [VISION.md](VISION.md). Operations: [RUN.md](RUN.md).

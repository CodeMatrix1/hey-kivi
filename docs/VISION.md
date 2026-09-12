# Vision

## What Hey Kivi is

Hey Kivi is a **single chat surface** over three kinds of personal data:

1. **Semantic memory (Hindsight)** — durable facts, preferences, and episodes extracted when content is retained.
2. **Dictation artifacts (SQLite + FTS5)** — immutable ASR and formatted transcripts you can find and polish.
3. **Lexical mappings (SQLite)** — explicit alias → canonical rules you teach in conversation.

Each user message is interpreted, optionally learned lexically, optionally retained (when configured), then routed to **cross-recall**, **find/polish**, or **general chat**. Every response carries a **DecisionTrace** so you can see why Kivi answered, retrieved a note, or abstained.

Phase 1 does **not** include live microphone dictation in the UI. The Golden Goose corpus replays ASR + formatted text through the same ingest path reviewers can reproduce. Text notes enter via **History** or `POST /dictations/{user_id}`.

## Product surfaces

| Surface | Where it lives | Role |
|---------|----------------|------|
| **Chats** | Browser `localStorage` | Multi-turn threads; optional demo seed from `demo_chats.json` (UI-only, not Hindsight) |
| **History** | Server SQLite | Dictation rows + FTS find; add text notes that flow through full ingest |
| **Reminders** | Browser `localStorage` | Client-side “remind me …” with date/time; no server push in Phase 1 |
| **Personalization** | Server SQLite | Lexical preferences and learning feed |
| **Developer tools** | Query library + traces | `query_cases.json` probes, metrics, `?dev=1` inspection |

**Chat vs memory:** With `KIVI_CHAT=true`, substantive chat retains to Hindsight (`kivi_chat=true`) but does **not** create dictation rows. Recall/find tool turns skip retain. Corpus import and text notes create dictations **and** retain. All paths share one Hindsight bank per user, separated by provenance headers.

**Session continuity:** The UI sends recent `context_messages` so same-thread follow-ups (e.g. “what exam am I preparing for?”) can be answered from the current conversation even before Hindsight retain catches up.

## How routing works

The interpreter sets flags on each turn:

- **`wants_dictation`** — find, open, or polish a specific past artifact (“Find my note about train seats and polish it”).
- **`wants_cross_recall`** — answer requires prior context (“What have I said about travel?” or “Pull together what I already said about the payments review”).
- **Both** can be true in one turn (e.g. prepare from memories then polish a linked note).

Greetings, spelling teaching (“It’s Aaditya, not Aditya”), and general knowledge stay on general or lexical paths without forced retrieval.

**Examples (Path A baseline):**

| You ask | Expected behaviour |
|---------|-------------------|
| Family visit — where are Maya and Arjun based? | **Answer** from `hist_001` / `hist_002` — Pune and Bengaluru; family-visit framing; no invented addresses |
| Payments review — pull together what I said | **Answer** from review/presentation memories; flag gaps if agenda/outcomes missing |
| What is my passport number? | **Abstain** — not in corpus |

See [RUN.md §6](RUN.md) for curl probes and example reply shapes.

## Memory layers (what each field means)

| Layer | Field / store | Meaning |
|-------|----------------|---------|
| **Formatted** | `dictations.formatted` | Written transcript — what the product treats as what you meant |
| **ASR** | `dictations.asr` | Raw speech-like text; preserved for audit and FTS; never rewritten in SQLite |
| **Lexical** | `lexical_mappings` | User-taught alias → canonical; applied to formatted text before retain and polish |
| **Hindsight** | Bank `kivi_<user_id>` | Semantic units from canonical retain payloads |
| **Provenance** | `corpus_ingestions`, headers | Links Hindsight hits back to `hist_*` / `d_note_*` dictation ids |

Formatted is the transcript; lexical is explicit spelling on top; Hindsight is what persists for cross-recall.

## Principles

1. **Grounded over fluent** — abstain rather than invent when recall/find lack support.
2. **Inspectable** — traces expose decision, tools, memories considered, and retain skips.
3. **Append-only artifacts** — dictations are not silently edited; polish is a separate find-path action.
4. **No self-memory** — assistant output is not retained as durable memory.
5. **User-taught lexicon** — spelling corrections are explicit mappings, not hidden prompt hacks.

## User control (Phase 1)

- **Teach** spellings and aliases in chat.
- **Inspect** every turn via Developer trace.
- **Reset** engineers’ data with `docker compose down -v` or per-user clear + re-import.
- **Correct** a wrong fact by stating the correction — new retain adds context; Hindsight is not edited in place.
- **No** in-app “forget this memory” button yet.

## Limitations we document honestly

- **“In Slack” / “around 5 PM”** — conversational hints only; find uses FTS + calendar day, not channel metadata or clock windows.
- **Provenance** — dictation ids live in SQLite `corpus_ingestions` and retain headers, not natively inside every Hindsight card.
- **Demo chats** — `demo_chats.json` seeds the sidebar only; pair with baseline or corpus for live recall.
- **Reminders** — localStorage only; no push notifications.
- **LLM providers** — Hey Kivi: Groq or Gemini (`LLM_PROVIDER`). Hindsight container: separate Groq config.
- **Per-user dictation ids** — same `hist_*` id can exist for different users (composite primary key); corpus import for a second user does not collide with baseline.

## Out of scope for Phase 1

Live ASR capture, Accept/Reject memory UI, multi-tenant auth, public hosting, and OpenAI/LiteLLM as Hey Kivi providers.

**Reviewer path:** restore `ops/baseline-volumes/*.tar.gz` → compose up → `/stats` → three chat probes. Full 500-row import is optional reproducibility only ([RUN.md §8](RUN.md)).

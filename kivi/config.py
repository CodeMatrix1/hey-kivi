"""Configuration and LLM prompts for Hey Kivi Phase 1."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from hindsight_pipeline_2.paths import DEFAULT_DB_PATH, PACKAGE_DIR

# ---------------------------------------------------------------------------
# Prompts (all LLM system strings live here)
# ---------------------------------------------------------------------------

RETAIN_MISSION = (
    "Extract durable, user-grounded semantic memories that are likely "
    "to remain useful in future conversations.\n\n"
    "Prioritize:\n"
    "- stable facts about the user\n"
    "- meaningful user preferences\n"
    "- durable work and project context\n"
    "- important decisions and commitments\n"
    "- meaningful experiences or episodes\n"
    "- useful relationships and entities grounded in the user's statements\n\n"
    "Ignore:\n"
    "- greetings and small talk\n"
    "- transient conversational details\n"
    "- one-off noise\n"
    "- information with no likely future value\n"
    "- unsupported assumptions or inferred facts\n\n"
    "Never invent facts.\n"
    "Treat explicit user statements as stronger evidence than inference.\n\n"
    "User-specific lexical/canonicalization mappings such as preferred "
    "spellings or alias-to-canonical transformations are handled by a "
    "separate Kivi lexical pipeline; do not attempt to create or maintain "
    "exact lexical replacement rules."
)

INTERPRET_SYSTEM = """
You are a turn interpreter. Decide whether this user message requires either
of two retrieval behaviors.

Return ONLY valid JSON with exactly these fields:

{
  "wants_dictation": bool,
  "wants_cross_recall": bool
}

Both flags may be true in the same turn. Prefer false for both when unsure.
Set a flag true only when its key test is clearly met.
Do not add any other fields.

## wants_dictation

Set to true when the user wants a SPECIFIC past user-generated artifact
retrieved or worked with — e.g. a note, message, draft, dictation, or document.

This includes open, show, find, summarize, rewrite, polish, or otherwise
operate on that specific past item.

Key test: "Does the user want that specific past artifact itself?"

True:
- "Find the note I wrote yesterday."
- "Polish my dictation from 5pm."
- "Find the note where I discussed the project."
- "Find my old draft and summarize it."

False (derived info only, not a specific artifact):
- "What did I tell you about my project?"
- "What have I said about this before?"
- "Summarize what I've said about the project."
- "Where / when did I discuss the project?"  (no find/open/show of a note)

## wants_cross_recall

Set to true when answering correctly requires the user's prior context
(stored history, memories, or past interactions), and the current message
plus general knowledge are not enough for a useful answer.

Key test: "Do I need the user's prior context to answer usefully?"

True:
- "What have I been working on recently?"
- "What did we decide about this?"
- "Have I mentioned this before?"
- "Based on what you know about me, what would I prefer?"
- "Summarize what I've said about the project."
- "Pull together what I've said about the review and presentation work."
- "What key points should I bring to the payments team review?"

False (no prior context required):
- "Explain what a database index is."
- "What is the capital of France?"
- "My name is Aaditya, not Aditya."
- "Use Kivi, not KIVI."

Do NOT set true merely because the topic is personal or might have been
discussed before. Prior context must actually be needed.

## Both true

Flags are independent. Set both when the user needs a specific past artifact
AND other prior context.

Example:
"Find my note from yesterday and tell me what we decided about the project."
→ wants_dictation = true, wants_cross_recall = true

If they ask for a specific past artifact (even to extract info from it),
use wants_dictation. If they only want information from history, use
wants_cross_recall.

## Both false

Leave both false for greetings, statements, advice, teaching moments,
clarifications that are not retrieval requests, and ordinary chat.
A separate general-chat reply handles those turns — do not force
retrieval just to avoid both being false.

Return ONLY the JSON object. No markdown or explanation.
""".strip()

LEXICAL_EXTRACT_SYSTEM = """
You extract ONLY explicit user-specific lexical mappings.

A lexical mapping means the user explicitly establishes that one
surface form should be written, called, or referred to using another
specific form.

Return JSON only:
{"mappings":[{"alias":"...","canonical":"...","kind":"name|spelling|alias|terminology"}]}

Return zero mappings unless the user's wording provides explicit
evidence for such a mapping.

Extract only mappings involving:
- the user's name or identity
- terms/names the user explicitly defines for their own projects,
  work, artifacts, concepts, or other user-specific entities
- explicit user-specific spelling preferences
- explicit user-specific aliases
- explicit terminology conventions established by the user

kind="name" ONLY when the user explicitly frames the mapping as their
name/identity (e.g. "my name is", "spell my name"). Project/product
terms use "terminology" or "alias" or "spelling", never "name".

alias = the surface form the user does NOT want used.
canonical = the user-preferred form.

Do NOT extract:
- general semantic preferences ("I prefer Python over Java")
- facts, episodes, relationships
- general world knowledge or synonyms
- mappings inferred only from spelling similarity
- mappings inferred from ordinary mentions
- mappings inferred from previous knowledge
- mappings the user did not explicitly establish
- preferred-name-only statements with no alternate surface
  ("I go by Aaditya", "Please use Aaditya when referring to me")

Examples:

"My name is Aaditya, not Aditya."
=> alias="Aditya", canonical="Aaditya", kind="name"

"Please spell my name Aaditya."
=> [] (no alternate surface form)

"I go by Aaditya."
=> []

"Use Kivi, not KIVI, for my project."
=> alias="KIVI", canonical="Kivi", kind="terminology"

"I prefer Python over Java."
=> []

"Aditya sent me the code."
=> []

Never invent an alias or canonical form.
Never normalize away the original surface form in the extracted result.
Extract exact strings as they appear in the user's message.
""".strip()

SYNTHESIZE_SYSTEM = """
Answer the user's question using the provided memories as evidence.

The memories describe things the user has previously told Kivi.
Synthesize them into a useful, natural answer to the user's current request.

Rules:
- Use facts, preferences, and episodes present in the memories.
- Combine related memories and ignore duplicates or noisy metadata.
- Do not dump raw memory cards, provenance headers, or Involving/When lines verbatim.
- Do not mention memory retrieval, memory cards, sources, or this prompt.
- Do not invent facts, destinations, landmarks, hotels, bookings, or travel advice.
- Do not invent work outcomes, meeting decisions, ticket IDs, credentials, or
  deliverable details that are not in the memories.
- Do not add generic tourism recommendations or generic workplace advice unless
  the user stated them.
- When the user asks to pull together, recap, or list key points, summarize what
  the memories say about that topic — even if details are partial or repetitive.
- If memories clearly mention the topic asked about, answer from them; do not say
  "I don't know" merely because the memories are repetitive or lack every detail.
- Say "I don't know" only when no memory relates to the question at all.
- Do not fill gaps with generic advice or world knowledge when the user asked about
  their own history.

Partial context (important):
- When memories are related but do not contain the exact detail asked for, state what
  IS known and what is NOT recorded. A concise explanatory answer is better than
  inventing the missing detail or listing raw memories.
- Travel examples: trip ideas without a hotel name, destinations considered but not
  booked, dates mentioned vaguely without a confirmed reservation.
- Work and app examples: a team review or presentation mentioned without outcomes,
  a project or feature named without status, prep for a meeting without agenda items,
  blockers raised without resolution, or a tool/app discussed without configuration
  details the user never gave.
- When the user asks to pull together, recap, or list key points for a meeting,
  review, launch, or trip, summarize supported facts first and note honestly what
  was never recorded.
- Return only the final answer.
"""

POLISH_SYSTEM = (
    "You polish a dictation transcript for a stated occasion. "
    "Preserve meaning. Remove synthetic scaffolding such as "
    "'activity log entry N' or 'Nth planning note'. "
    "Occasions may be personal (travel plan, message to a friend) or work "
    "(meeting update, team review readout, status note, presentation snippet). "
    "Match the tone to the occasion but never add facts, decisions, or details "
    "that are not in the transcript. "
    "Return ONLY the polished transcript text — no preamble, apology, or "
    "commentary about missing access to notes."
)

DICTATION_SELECT_SYSTEM = """
Select the reasonable source dictations that directly answer the user's request.

Return ONLY valid JSON:
{"selected_ids":["candidate id"],"reason":"brief evidence-based reason"}

Use only the supplied candidate records. Select an ID only when it is clearly
the source artifact the user wants. Return one ID unless the user explicitly
asks for multiple notes. Prefer original declarative notes that contain the
requested information. Prefer the most recent candidate when several are
near-duplicates of the same fact.
Reject candidates that are:
- a question, request, or instruction to Kivi rather than source content
- an echo/rephrasing of the current request
- meta-conversation such as asking what Kivi knows or thinks
- only a partial topical match

If none directly supports the request, return selected_ids=[]. Never invent a
candidate ID or content.
""".strip()

GENERAL_CHAT_SYSTEM = """
You are Hey Kivi, a concise, friendly assistant.

## When this call runs
This reply is used ONLY when the turn interpreter set both
wants_dictation=false and wants_cross_recall=false — i.e. the user is
not asking to fetch a past note/dictation and not asking you to answer
from their stored history.

Typical cases for this path:
- greetings and small talk ("hi", "thanks")
- statements, reflections, advice they want acknowledged
- ordinary questions answerable from general knowledge
- teaching a spelling/alias (a separate system may already confirm that)

## How to respond
- Be brief and natural (a few sentences max).
- Acknowledge what they said; do not invent that you looked up memories
  or opened a dictation unless they asked for that.
- If they shared something to remember, you may say you'll keep it in mind
  without claiming a specific memory tool ran.
- Do not dump a capability menu unless they ask what you can do.

Return plain reply text only. No JSON or markdown fences.
""".strip()

GENERAL_CHAT_FALLBACK = "How can I help you?"


DEFAULT_USER_ID = "golden_goose_eval_user"
ALLOWED_LLM_PROVIDERS = frozenset({"groq", "gemini"})


@dataclass(frozen=True)
class Settings:
    hindsight_base_url: str
    hindsight_api_key: str | None
    bank_prefix: str
    memory_backend: str  # hindsight only
    llm_provider: str
    db_path: Path
    recall_budget: str
    default_user_id: str = DEFAULT_USER_ID
    default_user_name: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
        if provider not in ALLOWED_LLM_PROVIDERS:
            raise ValueError(
                f"LLM_PROVIDER must be one of {sorted(ALLOWED_LLM_PROVIDERS)}; got {provider!r}"
            )
        backend = os.getenv("KIVI_MEMORY_BACKEND", "hindsight").strip().lower()
        if backend != "hindsight":
            backend = "hindsight"
        db = os.getenv("KIVI2_DB_PATH", str(DEFAULT_DB_PATH))
        default_name = os.getenv("KIVI_DEFAULT_USER_NAME", "").strip() or None
        return cls(
            hindsight_base_url=os.getenv("HINDSIGHT_BASE_URL", "http://localhost:8888").rstrip(
                "/"
            ),
            hindsight_api_key=os.getenv("HINDSIGHT_API_KEY") or None,
            bank_prefix=os.getenv("HINDSIGHT_BANK_PREFIX", "kivi").strip() or "kivi",
            memory_backend=backend,
            llm_provider=provider,
            db_path=Path(db),
            recall_budget=os.getenv("HINDSIGHT_RECALL_BUDGET", "mid"),
            default_user_id=os.getenv("KIVI_DEFAULT_USER_ID", DEFAULT_USER_ID).strip()
            or DEFAULT_USER_ID,
            default_user_name=default_name,
        )

    def require_llm(self) -> None:
        if self.llm_provider == "gemini":
            missing = [v for v in ("GEMINI_API_KEY", "GEMINI_MODEL") if not os.getenv(v)]
        else:
            missing = [v for v in ("GROQ_API_KEY", "GROQ_MODEL") if not os.getenv(v)]
        if missing:
            raise ValueError(f"Missing LLM env vars: {', '.join(missing)}")

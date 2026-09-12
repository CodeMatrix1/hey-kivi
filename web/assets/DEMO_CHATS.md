# Demo chat seed file

Demo conversations load from `demo_chats.json` into browser localStorage (sidebar chats). They are **not** stored on the server.

## File location

`hindsight_pipeline_2/web/assets/demo_chats.json`

Served at: `/static/assets/demo_chats.json`

## When chats are loaded

1. **Automatic** — on first visit when the sidebar has no conversations (empty localStorage).
2. **Settings** — **Load demo chats** merges conversations from the file (skips IDs already present).
3. **URL** — `?seed_chats=1` merges demo chats on page load (useful for refresh during review).

## Top-level shape

```json
{
  "version": 1,
  "description": "Optional note for authors",
  "conversations": [ /* ... */ ]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `version` | yes | Integer. Bump when you change seed content materially. |
| `description` | no | Human-readable note (ignored by the app). |
| `conversations` | yes | Array of conversation objects (may be empty). |

## Conversation object

```json
{
  "id": "conv_demo_payments",
  "title": "Payments review prep",
  "createdAt": "2026-09-10T09:00:00.000Z",
  "updatedAt": "2026-09-10T09:05:00.000Z",
  "lastUsedAt": "2026-09-10T09:05:00.000Z",
  "messages": [ /* see below */ ]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Stable unique id (e.g. `conv_demo_*`). Used for merge/dedup. |
| `title` | yes | Sidebar label. |
| `createdAt` | yes | ISO 8601 UTC timestamp. |
| `updatedAt` | yes | ISO 8601 UTC timestamp. |
| `lastUsedAt` | no | ISO 8601; defaults to `updatedAt` if omitted. Controls sort order. |
| `messages` | yes | Ordered user/assistant turns (at least one). |

## Message object

```json
{
  "id": "msg_user_1",
  "role": "user",
  "text": "What have I said about the payments team review?",
  "at": "2026-09-10T09:00:00.000Z"
}
```

```json
{
  "id": "msg_asst_1",
  "role": "assistant",
  "text": "You noted a payments team review on September 8 and presentation work on September 10.",
  "at": "2026-09-10T09:01:00.000Z",
  "trace": {
    "decision": "answer",
    "wants_cross_recall": true,
    "tools_used": ["hindsight_recall"],
    "memories_considered": [
      {
        "text": "Payments team review and presentation prep.",
        "source_dictation_id": "d_slack_1700"
      }
    ]
  },
  "metrics": {
    "elapsed_ms": 420,
    "llm_call_count": 2,
    "retain_call_count": 0
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Unique within the conversation. |
| `role` | yes | `"user"` or `"assistant"`. |
| `text` | yes | Message body (plain text). |
| `at` | yes | ISO 8601 UTC timestamp. |
| `trace` | no | Decision trace for assistant turns (powers **From history** blocks and personalization badge). |
| `metrics` | no | Turn metrics shown in developer tools. |

### Trace (optional, assistant messages)

Useful fields for demos:

- `decision` — `"answer"` | `"abstain"`
- `wants_cross_recall`, `wants_dictation` — booleans
- `tools_used` — e.g. `["hindsight_recall"]`, `["find_dictations", "polish_dictation"]`
- `memories_considered` — `[{ "text": "...", "source_dictation_id": "d_..." }]`
- `semantic_retain`, `semantic_retain_preview` — chat retain indicator
- `applied_preferences` — `[{ "observed": "Aditya", "preferred": "Aaditya" }]`
- `selected_dictation_id` — when find/polish selected a note

## Full minimal example

```json
{
  "version": 1,
  "description": "Golden Goose demo threads",
  "conversations": [
    {
      "id": "conv_demo_recall_maya",
      "title": "Family visit planning",
      "createdAt": "2026-09-08T14:00:00.000Z",
      "updatedAt": "2026-09-08T14:02:00.000Z",
      "lastUsedAt": "2026-09-08T14:02:00.000Z",
      "messages": [
        {
          "id": "msg_u1",
          "role": "user",
          "text": "Remind me where my sister Maya and brother Arjun are based.",
          "at": "2026-09-08T14:00:00.000Z"
        },
        {
          "id": "msg_a1",
          "role": "assistant",
          "text": "Maya is in Pune and Arjun is in Bengaluru.",
          "at": "2026-09-08T14:01:00.000Z",
          "trace": {
            "decision": "answer",
            "wants_cross_recall": true,
            "tools_used": ["hindsight_recall"],
            "memories_considered": [
              { "text": "Maya lives in Pune." },
              { "text": "Arjun is based in Bengaluru." }
            ]
          }
        }
      ]
    }
  ]
}
```

## Notes

- Demo chats are **UI-only**. They do not write to Hindsight or SQLite unless the user sends a new message.
- Pair recall demos with server seed data (`POST /seed`, corpus import, or baseline volume) so assistant answers match real memories.
- Use **Clear all conversations** in Settings before reloading if you want a clean re-import of the same IDs.

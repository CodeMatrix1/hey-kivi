import type { Conversation, DecisionTrace, LearningEvent, StoredMessage } from "../types";

export const CONVERSATIONS_STORAGE_KEY = "kivi_conversations_v1";
const CONV_KEY = CONVERSATIONS_STORAGE_KEY;
const LEARNING_KEY = "kivi_learning_feed_v1";

function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(CONV_KEY);
    return raw ? (JSON.parse(raw) as Conversation[]) : [];
  } catch {
    return [];
  }
}

function saveConversations(conversations: Conversation[]): void {
  localStorage.setItem(CONV_KEY, JSON.stringify(conversations));
}

/** When the user last tried chatting in this conversation (send), newest first. */
function lastChatAttemptTimestamp(conv: Conversation): number {
  if (conv.lastUsedAt) return new Date(conv.lastUsedAt).getTime();
  for (let i = conv.messages.length - 1; i >= 0; i--) {
    const message = conv.messages[i];
    if (message.role === "user") return new Date(message.at).getTime();
  }
  return new Date(conv.createdAt).getTime();
}

export function listConversations(): Conversation[] {
  return loadConversations().sort(
    (a, b) => lastChatAttemptTimestamp(b) - lastChatAttemptTimestamp(a),
  );
}

export function getConversation(id: string): Conversation | undefined {
  return loadConversations().find((c) => c.id === id);
}

export function clearAllConversations(): void {
  localStorage.removeItem(CONV_KEY);
}

export function renameConversation(id: string, title: string): Conversation | undefined {
  const trimmed = title.trim();
  if (!trimmed) return undefined;
  const all = loadConversations();
  const idx = all.findIndex((c) => c.id === id);
  if (idx < 0) return undefined;
  const conv = all[idx];
  conv.title = trimmed.length > 80 ? `${trimmed.slice(0, 79)}…` : trimmed;
  all[idx] = conv;
  saveConversations(all);
  return conv;
}

export function deleteConversation(id: string): boolean {
  const all = loadConversations();
  const next = all.filter((c) => c.id !== id);
  if (next.length === all.length) return false;
  saveConversations(next);
  return true;
}

export function createConversation(): Conversation {
  const now = new Date().toISOString();
  const conv: Conversation = {
    id: `conv_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    title: "New chat",
    createdAt: now,
    updatedAt: now,
    lastUsedAt: now,
    messages: [],
  };
  const all = loadConversations();
  all.unshift(conv);
  saveConversations(all);
  return conv;
}

const TITLE_SHORTCUTS: Array<[RegExp, string]> = [
  [/\bmachine learning\b/gi, "ML"],
  [/\bartificial intelligence\b/gi, "AI"],
];

export function deriveTitle(text: string, maxLen = 48): string {
  let t = text
    .replace(
      /^(For future reference,|I'm thinking ahead about this:|One preference of mine:|About this note[^:]*:\s*"?)\s*/i,
      "",
    )
    .replace(/^"+|"+$/g, "")
    .trim();

  for (const [pattern, replacement] of TITLE_SHORTCUTS) {
    t = t.replace(pattern, replacement);
  }

  const sentence = (t.split(/[.!?]/)[0] || t).trim();
  if (!sentence) return "New chat";
  return sentence.length > maxLen ? `${sentence.slice(0, maxLen - 1)}…` : sentence;
}

export function buildApiMessage(
  userText: string,
  dictationQuote?: string,
): string {
  const trimmed = userText.trim();
  if (!dictationQuote?.trim()) return trimmed;
  const quote = dictationQuote.trim();
  return `About this note I said: "${quote}"\n\n${trimmed}`;
}

function stripTraceForStorage(trace: DecisionTrace): DecisionTrace {
  return {
    wants_dictation: trace.wants_dictation,
    wants_cross_recall: trace.wants_cross_recall,
    applied_preferences: trace.applied_preferences,
    memories_considered: trace.memories_considered?.slice(0, 3),
    memories_retained: trace.memories_retained?.slice(0, 2),
    semantic_retain: trace.semantic_retain,
    semantic_retain_preview: trace.semantic_retain_preview,
    tools_used: trace.tools_used,
    decision: trace.decision,
    selected_dictation_id: trace.selected_dictation_id,
    selected_dictation_ids: trace.selected_dictation_ids,
    candidates: trace.candidates?.slice(0, 6).map((c) => ({
      id: c.id,
      formatted_preview: c.formatted_preview,
      created_at: c.created_at,
    })),
    llm_calls: trace.llm_calls,
  };
}

export function appendMessage(
  convId: string,
  message: StoredMessage,
): Conversation | undefined {
  const all = loadConversations();
  const idx = all.findIndex((c) => c.id === convId);
  if (idx < 0) return undefined;
  const conv = all[idx];
  if (message.trace) {
    message.trace = stripTraceForStorage(message.trace);
  }
  conv.messages.push(message);
  conv.updatedAt = new Date().toISOString();
  if (message.role === "user") {
    conv.lastUsedAt = conv.updatedAt;
  }
  if (conv.title === "New chat" && message.role === "user" && conv.messages.length === 1) {
    conv.title = deriveTitle(message.text);
  }
  all[idx] = conv;
  saveConversations(all);
  return conv;
}

export function getLearningFeed(): LearningEvent[] {
  try {
    const raw = localStorage.getItem(LEARNING_KEY);
    return raw ? (JSON.parse(raw) as LearningEvent[]) : [];
  } catch {
    return [];
  }
}

export function pushLearningFromTrace(trace: DecisionTrace): void {
  const retained = trace.memories_retained?.[0]?.text;
  const preview = trace.semantic_retain_preview;
  const summary = retained || preview;
  if (!summary && !trace.semantic_retain) return;
  const feed = getLearningFeed();
  feed.unshift({
    id: `learn_${Date.now()}`,
    at: new Date().toISOString(),
    summary: summary || "Kivi updated its understanding.",
    kind: trace.semantic_retain ? "learned" : "ignored",
  });
  localStorage.setItem(LEARNING_KEY, JSON.stringify(feed.slice(0, 30)));
}

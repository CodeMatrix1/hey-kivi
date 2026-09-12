import type {
  ChatResponse,
  ContextMessage,
  Dictation,
  HealthInfo,
  LexicalMapping,
  QueryCase,
} from "../types";

export async function getHealth(): Promise<HealthInfo> {
  const res = await fetch("/health");
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export interface PostChatOptions {
  context?: ContextMessage[];
  signal?: AbortSignal;
}

export async function postChat(
  userId: string,
  message: string,
  options?: PostChatOptions | AbortSignal,
): Promise<ChatResponse> {
  const opts: PostChatOptions =
    options instanceof AbortSignal ? { signal: options } : options || {};
  const body: Record<string, unknown> = { user_id: userId, message };
  if (opts.context && opts.context.length > 0) {
    body.context_messages = opts.context;
  }
  const res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: opts.signal,
  });
  if (!res.ok) {
    await res.text();
    throw new Error("request_failed");
  }
  return res.json();
}

export async function getLexical(userId: string): Promise<{ mappings: LexicalMapping[] }> {
  const res = await fetch(`/lexical/${encodeURIComponent(userId)}`);
  if (!res.ok) throw new Error("Failed to load preferences");
  return res.json();
}

export async function saveLexicalPreference(
  userId: string,
  body: { preferred: string; inputs: string[]; previous_preferred?: string },
): Promise<{ mappings: LexicalMapping[] }> {
  const res = await fetch(`/lexical/${encodeURIComponent(userId)}/preference`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Failed to save preference");
  }
  return res.json();
}

export async function getDictations(
  userId: string,
  limit = 500,
): Promise<{ count: number; returned: number; dictations: Dictation[] }> {
  const res = await fetch(
    `/dictations/${encodeURIComponent(userId)}?limit=${limit}`,
  );
  if (!res.ok) throw new Error("Failed to load dictations");
  return res.json();
}

export async function createTextDictation(
  userId: string,
  text: string,
): Promise<{ id: string; status: string }> {
  const res = await fetch(`/dictations/${encodeURIComponent(userId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Failed to add note");
  }
  return res.json();
}

export async function getQueryCases(): Promise<QueryCase[]> {
  const res = await fetch("/static/assets/query_cases.json");
  if (!res.ok) throw new Error("Failed to load query cases");
  return res.json();
}

export async function getDemoChatsFile(): Promise<unknown> {
  const res = await fetch("/static/assets/demo_chats.json");
  if (!res.ok) throw new Error("Failed to load demo chats");
  return res.json();
}

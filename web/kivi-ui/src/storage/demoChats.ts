import type { ChatMetrics, Conversation, DecisionTrace, StoredMessage } from "../types";
import { CONVERSATIONS_STORAGE_KEY } from "./conversations";

export const DEMO_CHATS_SEED_VERSION_KEY = "kivi_demo_chats_seed_version_v1";

export interface DemoChatsFile {
  version: number;
  description?: string;
  conversations: Conversation[];
}

export type DemoChatsImportMode = "replace_empty" | "merge";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseMessage(raw: unknown, index: number, convId: string): StoredMessage | null {
  if (!isRecord(raw)) return null;
  const role = raw.role;
  if (role !== "user" && role !== "assistant") return null;
  const text = typeof raw.text === "string" ? raw.text.trim() : "";
  if (!text) return null;
  const at = typeof raw.at === "string" ? raw.at : "";
  if (!at) return null;
  const id =
    typeof raw.id === "string" && raw.id.trim()
      ? raw.id.trim()
      : `msg_${convId}_${index}`;
  const message: StoredMessage = { id, role, text, at };
  if (isRecord(raw.trace)) {
    message.trace = raw.trace as DecisionTrace;
  }
  if (isRecord(raw.metrics)) {
    message.metrics = raw.metrics as unknown as ChatMetrics;
  }
  return message;
}

function parseConversation(raw: unknown, index: number): Conversation | null {
  if (!isRecord(raw)) return null;
  const id =
    typeof raw.id === "string" && raw.id.trim()
      ? raw.id.trim()
      : `conv_demo_${index}`;
  const title = typeof raw.title === "string" ? raw.title.trim() : "";
  if (!title) return null;
  const createdAt = typeof raw.createdAt === "string" ? raw.createdAt : "";
  const updatedAt = typeof raw.updatedAt === "string" ? raw.updatedAt : createdAt;
  if (!createdAt) return null;
  const messagesRaw = Array.isArray(raw.messages) ? raw.messages : [];
  const messages: StoredMessage[] = [];
  for (let i = 0; i < messagesRaw.length; i++) {
    const msg = parseMessage(messagesRaw[i], i, id);
    if (msg) messages.push(msg);
  }
  if (messages.length === 0) return null;
  const lastUsedAt =
    typeof raw.lastUsedAt === "string" ? raw.lastUsedAt : updatedAt || createdAt;
  return {
    id,
    title,
    createdAt,
    updatedAt: updatedAt || createdAt,
    lastUsedAt,
    messages,
  };
}

/** Parse and validate demo_chats.json payload. */
export function parseDemoChatsFile(data: unknown): DemoChatsFile {
  if (!isRecord(data)) {
    throw new Error("demo_chats.json must be a JSON object");
  }
  const version = data.version;
  if (typeof version !== "number" || !Number.isFinite(version)) {
    throw new Error("demo_chats.json requires a numeric version");
  }
  const conversationsRaw = Array.isArray(data.conversations) ? data.conversations : [];
  const conversations: Conversation[] = [];
  const seenIds = new Set<string>();
  for (let i = 0; i < conversationsRaw.length; i++) {
    const conv = parseConversation(conversationsRaw[i], i);
    if (!conv) continue;
    if (seenIds.has(conv.id)) {
      throw new Error(`duplicate conversation id: ${conv.id}`);
    }
    seenIds.add(conv.id);
    conversations.push(conv);
  }
  return {
    version,
    description: typeof data.description === "string" ? data.description : undefined,
    conversations,
  };
}

function loadStoredConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(CONVERSATIONS_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Conversation[]) : [];
  } catch {
    return [];
  }
}

function saveStoredConversations(conversations: Conversation[]): void {
  localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(conversations));
}

export function getDemoChatsSeedVersion(): number {
  try {
    const raw = localStorage.getItem(DEMO_CHATS_SEED_VERSION_KEY);
    return raw ? Number.parseInt(raw, 10) || 0 : 0;
  } catch {
    return 0;
  }
}

function setDemoChatsSeedVersion(version: number): void {
  localStorage.setItem(DEMO_CHATS_SEED_VERSION_KEY, String(version));
}

export interface ImportDemoChatsResult {
  imported: number;
  skipped: number;
  total: number;
  fileVersion: number;
}

/** Import parsed demo conversations into localStorage. */
export function importDemoChats(
  file: DemoChatsFile,
  mode: DemoChatsImportMode,
): ImportDemoChatsResult {
  const existing = loadStoredConversations();
  let next: Conversation[];
  let imported = 0;
  let skipped = 0;

  if (mode === "replace_empty") {
    if (existing.length > 0) {
      return {
        imported: 0,
        skipped: file.conversations.length,
        total: existing.length,
        fileVersion: file.version,
      };
    }
    next = [...file.conversations];
    imported = next.length;
  } else {
    const byId = new Map(existing.map((c) => [c.id, c]));
    for (const conv of file.conversations) {
      if (byId.has(conv.id)) {
        skipped += 1;
        continue;
      }
      byId.set(conv.id, conv);
      imported += 1;
    }
    next = Array.from(byId.values());
  }

  saveStoredConversations(next);
  if (imported > 0) {
    setDemoChatsSeedVersion(file.version);
  }

  return {
    imported,
    skipped,
    total: next.length,
    fileVersion: file.version,
  };
}

export async function loadAndImportDemoChats(
  fetchFile: () => Promise<unknown>,
  mode: DemoChatsImportMode,
): Promise<ImportDemoChatsResult> {
  const raw = await fetchFile();
  const file = parseDemoChatsFile(raw);
  return importDemoChats(file, mode);
}

import type {
  ChatMetrics,
  Conversation,
  DecisionTrace,
  StoredMessage,
  Topic,
  TopicNote,
} from "../types";
import { CONVERSATIONS_STORAGE_KEY } from "./conversations";
import { TOPICS_STORAGE_KEY } from "./topics";

export const DEMO_CHATS_SEED_VERSION_KEY = "kivi_demo_chats_seed_version_v1";

export interface DemoChatsFile {
  version: number;
  description?: string;
  conversations: Conversation[];
  topics?: Topic[];
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

function parseTopicNote(raw: unknown, index: number, topicId: string): TopicNote | null {
  if (!isRecord(raw)) return null;
  const text = typeof raw.text === "string" ? raw.text.trim() : "";
  if (!text) return null;
  const type = raw.type;
  if (type !== "decision" && type !== "context" && type !== "open") return null;
  const createdAt = typeof raw.createdAt === "string" ? raw.createdAt : "";
  const updatedAt = typeof raw.updatedAt === "string" ? raw.updatedAt : createdAt;
  if (!createdAt) return null;
  const id =
    typeof raw.id === "string" && raw.id.trim()
      ? raw.id.trim()
      : `tnote_${topicId}_${index}`;
  const note: TopicNote = {
    id,
    text,
    type,
    createdAt,
    updatedAt: updatedAt || createdAt,
  };
  if (typeof raw.sourceConversationId === "string" && raw.sourceConversationId.trim()) {
    note.sourceConversationId = raw.sourceConversationId.trim();
  }
  if (typeof raw.sourceMessageId === "string" && raw.sourceMessageId.trim()) {
    note.sourceMessageId = raw.sourceMessageId.trim();
  }
  if (typeof raw.sourceConversationTitle === "string" && raw.sourceConversationTitle.trim()) {
    note.sourceConversationTitle = raw.sourceConversationTitle.trim();
  }
  return note;
}

function parseTopic(raw: unknown, index: number): Topic | null {
  if (!isRecord(raw)) return null;
  const id =
    typeof raw.id === "string" && raw.id.trim()
      ? raw.id.trim()
      : `topic_demo_${index}`;
  const name = typeof raw.name === "string" ? raw.name.trim() : "";
  if (!name) return null;
  const createdAt = typeof raw.createdAt === "string" ? raw.createdAt : "";
  const updatedAt = typeof raw.updatedAt === "string" ? raw.updatedAt : createdAt;
  if (!createdAt) return null;
  const notesRaw = Array.isArray(raw.notes) ? raw.notes : [];
  const notes: TopicNote[] = [];
  for (let i = 0; i < notesRaw.length; i++) {
    const note = parseTopicNote(notesRaw[i], i, id);
    if (note) notes.push(note);
  }
  const conversationIds = Array.isArray(raw.conversationIds)
    ? raw.conversationIds.filter((c): c is string => typeof c === "string" && !!c.trim())
    : [];
  return {
    id,
    name,
    notes,
    conversationIds,
    createdAt,
    updatedAt: updatedAt || createdAt,
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
  const topicsRaw = Array.isArray(data.topics) ? data.topics : [];
  const topics: Topic[] = [];
  const seenTopicIds = new Set<string>();
  for (let i = 0; i < topicsRaw.length; i++) {
    const topic = parseTopic(topicsRaw[i], i);
    if (!topic) continue;
    if (seenTopicIds.has(topic.id)) {
      throw new Error(`duplicate topic id: ${topic.id}`);
    }
    seenTopicIds.add(topic.id);
    topics.push(topic);
  }
  return {
    version,
    description: typeof data.description === "string" ? data.description : undefined,
    conversations,
    topics: topics.length > 0 ? topics : undefined,
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

function loadStoredTopics(): Topic[] {
  try {
    const raw = localStorage.getItem(TOPICS_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Topic[]) : [];
  } catch {
    return [];
  }
}

function saveStoredTopics(topics: Topic[]): void {
  localStorage.setItem(TOPICS_STORAGE_KEY, JSON.stringify(topics));
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
  topicsImported: number;
  topicsSkipped: number;
  topicsTotal: number;
  fileVersion: number;
}

/** Import parsed demo conversations into localStorage. */
function importDemoTopics(
  seedTopics: Topic[] | undefined,
  mode: DemoChatsImportMode,
): { imported: number; skipped: number; total: number } {
  if (!seedTopics?.length) {
    const existing = loadStoredTopics();
    return { imported: 0, skipped: 0, total: existing.length };
  }
  const existing = loadStoredTopics();
  let next: Topic[];
  let imported = 0;
  let skipped = 0;

  if (mode === "replace_empty") {
    if (existing.length > 0) {
      return {
        imported: 0,
        skipped: seedTopics.length,
        total: existing.length,
      };
    }
    next = [...seedTopics];
    imported = next.length;
  } else {
    const byId = new Map(existing.map((t) => [t.id, t]));
    for (const topic of seedTopics) {
      if (byId.has(topic.id)) {
        skipped += 1;
        continue;
      }
      byId.set(topic.id, topic);
      imported += 1;
    }
    next = Array.from(byId.values());
  }

  if (imported > 0) {
    saveStoredTopics(next);
  }

  return {
    imported,
    skipped,
    total: imported > 0 ? next.length : existing.length,
  };
}

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
      const topicResult = importDemoTopics(file.topics, mode);
      return {
        imported: 0,
        skipped: file.conversations.length,
        total: existing.length,
        topicsImported: topicResult.imported,
        topicsSkipped: topicResult.skipped,
        topicsTotal: topicResult.total,
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
  const topicResult = importDemoTopics(file.topics, mode);
  if (imported > 0 || topicResult.imported > 0) {
    setDemoChatsSeedVersion(file.version);
  }

  return {
    imported,
    skipped,
    total: next.length,
    topicsImported: topicResult.imported,
    topicsSkipped: topicResult.skipped,
    topicsTotal: topicResult.total,
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

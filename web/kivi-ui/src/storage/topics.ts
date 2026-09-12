import type { Topic, TopicNote, TopicNoteType } from "../types";

export const TOPICS_STORAGE_KEY = "kivi_topics_v1";

function loadRaw(): Topic[] {
  try {
    const raw = localStorage.getItem(TOPICS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Topic[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveAll(topics: Topic[]): void {
  localStorage.setItem(TOPICS_STORAGE_KEY, JSON.stringify(topics));
}

export function listTopics(): Topic[] {
  return loadRaw().sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
  );
}

export function getTopic(id: string): Topic | undefined {
  return loadRaw().find((t) => t.id === id);
}

export function createTopic(name: string): Topic {
  const trimmed = name.trim();
  if (!trimmed) {
    throw new Error("Topic name is required");
  }
  const now = new Date().toISOString();
  const topic: Topic = {
    id: `topic_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name: trimmed.length > 80 ? `${trimmed.slice(0, 79)}…` : trimmed,
    notes: [],
    conversationIds: [],
    createdAt: now,
    updatedAt: now,
  };
  const all = loadRaw();
  all.unshift(topic);
  saveAll(all);
  return topic;
}

export interface AddTopicNoteInput {
  text: string;
  type: TopicNoteType;
  sourceConversationId: string;
  sourceMessageId: string;
  sourceConversationTitle?: string;
}

export function addNote(topicId: string, input: AddTopicNoteInput): TopicNote {
  if (!input.sourceConversationId?.trim() || !input.sourceMessageId?.trim()) {
    throw new Error("Topic notes require source conversation and message ids");
  }
  const text = input.text.trim();
  if (!text) {
    throw new Error("Note text is required");
  }
  const all = loadRaw();
  const idx = all.findIndex((t) => t.id === topicId);
  if (idx < 0) {
    throw new Error("Topic not found");
  }
  const now = new Date().toISOString();
  const note: TopicNote = {
    id: `tnote_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    text,
    type: input.type,
    sourceConversationId: input.sourceConversationId,
    sourceMessageId: input.sourceMessageId,
    sourceConversationTitle: input.sourceConversationTitle,
    createdAt: now,
    updatedAt: now,
  };
  const topic = all[idx];
  topic.notes.unshift(note);
  topic.updatedAt = now;
  if (!topic.conversationIds.includes(input.sourceConversationId)) {
    topic.conversationIds.push(input.sourceConversationId);
  }
  all[idx] = topic;
  saveAll(all);
  return note;
}

export function linkConversation(topicId: string, conversationId: string): Topic | null {
  if (!conversationId?.trim()) return null;
  const all = loadRaw();
  const idx = all.findIndex((t) => t.id === topicId);
  if (idx < 0) return null;
  const topic = all[idx];
  if (topic.conversationIds.includes(conversationId)) {
    return topic;
  }
  topic.conversationIds.push(conversationId);
  topic.updatedAt = new Date().toISOString();
  all[idx] = topic;
  saveAll(all);
  return topic;
}

export function saveNoteAndLinkConversation(
  topicId: string,
  input: AddTopicNoteInput,
): TopicNote {
  const note = addNote(topicId, input);
  linkConversation(topicId, input.sourceConversationId);
  return note;
}

export function updateTopicName(topicId: string, name: string): Topic | null {
  const trimmed = name.trim();
  if (!trimmed) {
    throw new Error("Topic name is required");
  }
  const all = loadRaw();
  const idx = all.findIndex((t) => t.id === topicId);
  if (idx < 0) return null;
  const topic = all[idx];
  topic.name = trimmed.length > 80 ? `${trimmed.slice(0, 79)}…` : trimmed;
  topic.updatedAt = new Date().toISOString();
  all[idx] = topic;
  saveAll(all);
  return topic;
}

export interface ManualTopicNoteInput {
  text: string;
  type: TopicNoteType;
}

export function addManualNote(topicId: string, input: ManualTopicNoteInput): TopicNote {
  const text = input.text.trim();
  if (!text) {
    throw new Error("Note text is required");
  }
  const all = loadRaw();
  const idx = all.findIndex((t) => t.id === topicId);
  if (idx < 0) {
    throw new Error("Topic not found");
  }
  const now = new Date().toISOString();
  const note: TopicNote = {
    id: `tnote_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    text,
    type: input.type,
    createdAt: now,
    updatedAt: now,
  };
  const topic = all[idx];
  topic.notes.unshift(note);
  topic.updatedAt = now;
  all[idx] = topic;
  saveAll(all);
  return note;
}

export interface UpdateTopicNoteInput {
  text?: string;
  type?: TopicNoteType;
}

export function updateNote(
  topicId: string,
  noteId: string,
  input: UpdateTopicNoteInput,
): TopicNote | null {
  const all = loadRaw();
  const topicIdx = all.findIndex((t) => t.id === topicId);
  if (topicIdx < 0) return null;
  const topic = all[topicIdx];
  const noteIdx = topic.notes.findIndex((n) => n.id === noteId);
  if (noteIdx < 0) return null;
  const note = topic.notes[noteIdx];
  if (input.text !== undefined) {
    const text = input.text.trim();
    if (!text) {
      throw new Error("Note text is required");
    }
    note.text = text;
  }
  if (input.type !== undefined) {
    note.type = input.type;
  }
  const now = new Date().toISOString();
  note.updatedAt = now;
  topic.updatedAt = now;
  topic.notes[noteIdx] = note;
  all[topicIdx] = topic;
  saveAll(all);
  return note;
}

export function deleteTopic(id: string): boolean {
  const all = loadRaw();
  const next = all.filter((t) => t.id !== id);
  if (next.length === all.length) return false;
  saveAll(next);
  return true;
}

/** Test helper */
export function clearAllTopics(): void {
  localStorage.removeItem(TOPICS_STORAGE_KEY);
}

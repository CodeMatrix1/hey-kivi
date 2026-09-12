import type { TopicNote, TopicNoteType } from "../types";

const TYPE_LABELS: Record<TopicNoteType, string> = {
  decision: "Decisions",
  context: "Context",
  open: "Open",
};

export const TOPIC_NOTE_TYPE_OPTIONS: { value: TopicNoteType; label: string }[] = [
  { value: "decision", label: "Decision" },
  { value: "context", label: "Context" },
  { value: "open", label: "Open" },
];

export function topicNoteTypeLabel(type: TopicNoteType): string {
  return TYPE_LABELS[type];
}

export function classifyNoteType(text: string): TopicNoteType {
  const lower = text.toLowerCase();
  if (
    /\b(unresolved|open question|still need|need to figure|blocked|tbd|pending|faulty|broken|wrong|incorrect|is that right|is this right|not sure|haven't figured|not figured|issue|problem)\b/.test(
      lower,
    )
  ) {
    return "open";
  }
  if (
    /\b(decided|decision|going with|will use|we('re| are) using|chose|switch(ed)? to)\b/.test(
      lower,
    )
  ) {
    return "decision";
  }
  return "context";
}

export function proposeNoteFromMessage(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return "";
  const sentence = (trimmed.split(/[.!?]/)[0] || trimmed).trim();
  if (sentence.length <= 160) return sentence;
  return `${sentence.slice(0, 157)}…`;
}

export function normalizeNoteText(text: string): string {
  return text.trim().toLowerCase().replace(/\s+/g, " ");
}

export function isDuplicateNote(text: string, existingNotes: TopicNote[]): boolean {
  const norm = normalizeNoteText(text);
  if (!norm) return true;
  return existingNotes.some((note) => {
    const existing = normalizeNoteText(note.text);
    return existing === norm || existing.includes(norm) || norm.includes(existing);
  });
}

export function groupNotesByType(
  notes: TopicNote[],
): Array<{ type: TopicNoteType; label: string; notes: TopicNote[] }> {
  const order: TopicNoteType[] = ["decision", "context", "open"];
  return order
    .map((type) => ({
      type,
      label: TYPE_LABELS[type],
      notes: notes.filter((n) => n.type === type),
    }))
    .filter((group) => group.notes.length > 0);
}

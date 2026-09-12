import type { Conversation } from "../types";

function lastActivityTimestamp(conv: Conversation): number {
  if (conv.lastUsedAt) return new Date(conv.lastUsedAt).getTime();
  if (conv.updatedAt) return new Date(conv.updatedAt).getTime();
  return new Date(conv.createdAt).getTime();
}

export interface ConversationGroup {
  label: string;
  conversations: Conversation[];
}

/** Human-facing title for the sidebar (does not change stored title). */
export function polishConversationTitle(title: string): string {
  const trimmed = title.trim();
  if (!trimmed || trimmed === "New chat") return trimmed;

  const lower = trimmed.toLowerCase();

  const shortcuts: Array<[RegExp, string]> = [
    [/remind.*paymen/i, "Payment review"],
    [/paymen.*team|team re/i, "Payments team"],
    [/family|address.*famil|what have i (?:said|mentioned) about ho/i, "Family locations"],
    [/spell.*name|name spell|how should.*spell/i, "Name spelling"],
    [/travel|trip/i, "Travel planning"],
    [/train/i, "Train note"],
    [/summarize what i/i, "What I've shared"],
    [/convo\s*1/i, "Getting started"],
  ];

  for (const [pattern, label] of shortcuts) {
    if (pattern.test(lower)) return label;
  }

  let t = trimmed
    .replace(/^remind me (?:to |about |abt |that )?/i, "")
    .replace(/^what have i (?:said|mentioned|told you) about /i, "")
    .replace(/^how should (?:you )?spell my /i, "Name spelling")
    .replace(/^i have a /i, "")
    .replace(/^help me /i, "")
    .trim();

  if (!t) return trimmed;
  if (t.length > 0) {
    t = t.charAt(0).toUpperCase() + t.slice(1);
  }
  return t.length > 48 ? `${t.slice(0, 47)}…` : t;
}

export function groupConversations(
  conversations: Conversation[],
  now: Date = new Date(),
): ConversationGroup[] {
  const startOfToday = new Date(now);
  startOfToday.setHours(0, 0, 0, 0);
  const todayMs = startOfToday.getTime();

  const today: Conversation[] = [];
  const earlier: Conversation[] = [];

  for (const conv of conversations) {
    if (lastActivityTimestamp(conv) >= todayMs) {
      today.push(conv);
    } else {
      earlier.push(conv);
    }
  }

  const groups: ConversationGroup[] = [];
  if (today.length > 0) groups.push({ label: "Today", conversations: today });
  if (earlier.length > 0) groups.push({ label: "Earlier", conversations: earlier });
  return groups;
}

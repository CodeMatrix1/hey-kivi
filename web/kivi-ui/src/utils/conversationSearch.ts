import type { Conversation } from "../types";
import { polishConversationTitle } from "./conversationDisplay";

export function searchConversations(
  conversations: Conversation[],
  query: string,
): Conversation[] {
  const q = query.trim().toLowerCase();
  if (!q) return conversations;

  return conversations.filter((conv) => {
    if (conv.title.toLowerCase().includes(q)) return true;
    if (polishConversationTitle(conv.title).toLowerCase().includes(q)) return true;
    return conv.messages.some(
      (m) =>
        (m.role === "user" || m.role === "assistant") &&
        m.text.toLowerCase().includes(q),
    );
  });
}

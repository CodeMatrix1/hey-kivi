import type { ContextMessage, StoredMessage } from "../types";

const MAX_TURNS = 3;

/** Build up to 3 prior user+assistant turn pairs (oldest first) for /chat context. */
export function buildChatContext(messages: StoredMessage[]): ContextMessage[] {
  const pairs: ContextMessage[][] = [];
  let i = messages.length - 1;

  while (i >= 0 && pairs.length < MAX_TURNS) {
    if (messages[i].role !== "assistant") {
      i--;
      continue;
    }
    const assistant = messages[i];
    const user = i > 0 && messages[i - 1].role === "user" ? messages[i - 1] : null;
    if (!user) {
      i--;
      continue;
    }
    pairs.unshift([
      { role: "user", content: user.text },
      { role: "assistant", content: assistant.text },
    ]);
    i -= 2;
  }

  return pairs.flat();
}

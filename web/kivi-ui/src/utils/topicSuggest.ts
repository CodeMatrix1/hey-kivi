import type { Topic, TopicNoteDraft } from "../types";
import { canShowAutoPrompt } from "../storage/topicSuggestState";
import {
  classifyNoteType,
  isDuplicateNote,
  proposeNoteFromMessage,
} from "./topicNotes";

const GREETING_RE =
  /^(hi|hello|hey|thanks|thank you|ok|okay|sure|got it|sounds good|cool)[\s!.?]*$/i;

const DURABLE_RE =
  /\b(decided|decision|going with|will use|we(?:'re| are) using|chose|switch(?:ed)? to|unresolved|open question|still need|need to|blocked|requirement|constraint|handling|confirmed|must|should not|deadline|faulty|broken|bug|bugs|issue|issues|problem|problems|wrong|incorrect|fails|failing|doesn't work|does not work|not sure|is that right|is this right|haven't figured|hasn't figured|not figured|wondering if|should we|what about)\b/i;

function topicNameInMessage(topicName: string, message: string): boolean {
  const name = topicName.trim().toLowerCase();
  if (!name) return false;
  const tokens = name.split(/\s+/).filter((t) => t.length >= 2);
  if (tokens.length === 0) return false;
  const lower = message.toLowerCase();
  return tokens.every((token) => lower.includes(token));
}

function isGreetingOrAck(text: string): boolean {
  const trimmed = text.trim();
  if (trimmed.length < 20) return true;
  return GREETING_RE.test(trimmed);
}

function hasDurableSignal(text: string): boolean {
  return DURABLE_RE.test(text);
}

export interface AutoSuggestInput {
  conversationId: string;
  messageId: string;
  messageText: string;
  topics: Topic[];
}

export interface AutoSuggestResult {
  topicId: string;
  topicName: string;
  drafts: TopicNoteDraft[];
}

/**
 * Heuristic MVP auto-suggest. LLM worthiness is TODO.
 */
export function maybeAutoSuggestTopicNotes(
  input: AutoSuggestInput,
): AutoSuggestResult | null {
  const { conversationId, messageId, messageText, topics } = input;
  const text = messageText.trim();
  if (!text || isGreetingOrAck(text) || !hasDurableSignal(text)) {
    return null;
  }

  for (const topic of topics) {
    if (!topicNameInMessage(topic.name, text)) continue;
    if (!canShowAutoPrompt(conversationId, topic.id, messageId)) continue;
    if (isDuplicateNote(proposeNoteFromMessage(text), topic.notes)) continue;

    const proposed = proposeNoteFromMessage(text);
    if (!proposed) continue;

    return {
      topicId: topic.id,
      topicName: topic.name,
      drafts: [
        {
          text: proposed,
          type: classifyNoteType(text),
          sourceConversationId: conversationId,
          sourceMessageId: messageId,
          sourceMessageText: text,
        },
      ],
    };
  }

  return null;
}

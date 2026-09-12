const STORAGE_KEY = "kivi_topic_suggest_state_v1";
export const MAX_AUTO_PROMPTS_PER_CONVERSATION = 2;

export interface ConversationSuggestState {
  promptCount: number;
  rejectedTopicIds: string[];
  suggestedMessageIds: string[];
}

type SuggestStateMap = Record<string, ConversationSuggestState>;

function emptyState(): ConversationSuggestState {
  return { promptCount: 0, rejectedTopicIds: [], suggestedMessageIds: [] };
}

function loadRaw(): SuggestStateMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as SuggestStateMap;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveRaw(map: SuggestStateMap): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
}

export function getSuggestState(conversationId: string): ConversationSuggestState {
  return loadRaw()[conversationId] ?? emptyState();
}

function updateState(
  conversationId: string,
  updater: (state: ConversationSuggestState) => ConversationSuggestState,
): ConversationSuggestState {
  const map = loadRaw();
  const next = updater(map[conversationId] ?? emptyState());
  map[conversationId] = next;
  saveRaw(map);
  return next;
}

export function canShowAutoPrompt(
  conversationId: string,
  topicId: string,
  messageId: string,
): boolean {
  const state = getSuggestState(conversationId);
  if (state.promptCount >= MAX_AUTO_PROMPTS_PER_CONVERSATION) return false;
  if (state.suggestedMessageIds.includes(messageId)) return false;
  if (state.rejectedTopicIds.includes(topicId)) return false;
  return true;
}

/** Call when an automatic suggestion card is displayed. */
export function recordPromptShown(conversationId: string, messageId: string): void {
  updateState(conversationId, (state) => ({
    ...state,
    promptCount: state.promptCount + 1,
    suggestedMessageIds: state.suggestedMessageIds.includes(messageId)
      ? state.suggestedMessageIds
      : [...state.suggestedMessageIds, messageId],
  }));
}

/** Call on dismiss/reject of an automatic suggestion (promptCount already consumed on show). */
export function recordPromptDismissed(conversationId: string, topicId: string): void {
  updateState(conversationId, (state) => ({
    ...state,
    rejectedTopicIds: state.rejectedTopicIds.includes(topicId)
      ? state.rejectedTopicIds
      : [...state.rejectedTopicIds, topicId],
  }));
}

export function clearSuggestState(): void {
  localStorage.removeItem(STORAGE_KEY);
}

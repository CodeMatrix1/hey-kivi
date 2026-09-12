export interface HealthInfo {
  ok: boolean;
  kivi_chat?: boolean;
  default_user_id: string;
  default_user_name?: string;
  ui_asset_version?: number;
}

export interface ChatMetrics {
  elapsed_ms: number;
  llm_call_count: number;
  retain_call_count: number;
  cost_usd?: number;
  db_delta?: Record<string, number>;
}

export interface DecisionTrace {
  wants_dictation?: boolean;
  wants_cross_recall?: boolean;
  applied_preferences?: Array<{ observed?: string; preferred?: string }>;
  memories_considered?: Array<{ text?: string; source_dictation_id?: string }>;
  memories_retained?: Array<{ text?: string }>;
  semantic_retain?: boolean;
  semantic_retain_preview?: string;
  tools_used?: string[];
  decision?: string;
  reason?: string;
  llm_calls?: Array<Record<string, unknown>>;
  selected_dictation_id?: string;
  selected_dictation_ids?: string[];
  candidates?: Array<{
    id: string;
    formatted_preview?: string;
    created_at?: string;
  }>;
}

export interface ContextMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  reply: string;
  trace: DecisionTrace;
  metrics?: ChatMetrics;
}

export interface Reminder {
  id: string;
  name: string;
  message: string;
  dueAt: string;
  createdAt: string;
  sourceConversationId?: string;
  sourceConversationTitle?: string;
}

export interface ReminderDraft {
  name: string;
  message: string;
  dueAt: string;
  sourceConversationId?: string;
  sourceConversationTitle?: string;
}

export type ReminderParseResult =
  | { kind: "not_reminder" }
  | { kind: "confirm"; draft: ReminderDraft }
  | { kind: "need_content"; dueAt: string };

export interface StoredMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  trace?: DecisionTrace;
  metrics?: ChatMetrics;
  at: string;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  lastUsedAt?: string;
  messages: StoredMessage[];
}

export interface LexicalMapping {
  alias: string;
  canonical: string;
  kind?: string;
}

export interface Dictation {
  id: string;
  asr: string;
  formatted: string;
  created_at: string;
}

export interface QueryCase {
  id: string;
  category: string;
  title: string;
  message: string;
}

export interface LearningEvent {
  id: string;
  at: string;
  summary: string;
  kind: "learned" | "ignored";
}

export interface PendingDictationContext {
  formatted: string;
  asr?: string;
}

export type AppView =
  | "chat"
  | "history"
  | "historyDetail"
  | "reminders"
  | "personalization"
  | "settings"
  | "developer";

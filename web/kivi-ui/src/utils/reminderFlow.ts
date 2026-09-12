import type { ReminderParseResult } from "../types";
import { evaluateReminderTrigger, buildDraftFromContent } from "./reminderTrigger";

export const LONG_MESSAGE_CONTENT_PROMPT =
  "What would you like the reminder to say?";

export const REMINDER_REJECTED_MESSAGE = "Reminder rejected.";
export const REMINDER_SAVED_MESSAGE = "Reminder saved.";

export function parseReminderMessage(
  text: string,
  now: Date = new Date(),
): ReminderParseResult {
  return evaluateReminderTrigger(text, now);
}

export function parseSuppliedReminderContent(
  content: string,
  dueAt: string,
): ReminderParseResult {
  const draft = buildDraftFromContent(content, dueAt);
  return { kind: "confirm", draft };
}

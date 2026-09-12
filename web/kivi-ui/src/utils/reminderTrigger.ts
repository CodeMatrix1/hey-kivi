import { REMINDER_CONTENT_MAX_LENGTH } from "./reminderConstants";
import { extractReminderContent } from "./reminderExtract";
import type { ReminderDraft, ReminderParseResult } from "../types";
import { hasRecognizableDateTime, isDueAtInFuture, resolveDueAt } from "./reminderTime";

const REMIND_PATTERN = /\bremind\b/i;

export function containsRemindKeyword(text: string): boolean {
  return REMIND_PATTERN.test(text);
}

export function evaluateReminderTrigger(
  text: string,
  now: Date = new Date(),
): ReminderParseResult {
  if (!containsRemindKeyword(text)) {
    return { kind: "not_reminder" };
  }
  if (!hasRecognizableDateTime(text)) {
    return { kind: "not_reminder" };
  }
  const dueAt = resolveDueAt(text, now);
  if (!dueAt || !isDueAtInFuture(dueAt, now)) {
    return { kind: "not_reminder" };
  }

  if (text.length > REMINDER_CONTENT_MAX_LENGTH) {
    return { kind: "need_content", dueAt };
  }

  const { name, message } = extractReminderContent(text);
  const draft: ReminderDraft = { name, message, dueAt };
  return { kind: "confirm", draft };
}

export function buildDraftFromContent(
  content: string,
  dueAt: string,
): ReminderDraft {
  const trimmed = content.trim();
  const { name, message } = trimmed
    ? extractReminderContent(trimmed)
    : { name: "Reminder", message: "Reminder" };
  return { name, message: message || name, dueAt };
}

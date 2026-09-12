import { findTemporalExpression } from "./reminderTime";

const REMIND_PREFIX = /^\s*(?:can you\s+)?(?:please\s+)?remind\s+me\s+(?:to|about|abt)\s+/i;
const REMIND_SUFFIX = /\s+(?:please\s+)?remind\s+me\s+(?:to|about|abt)\s+/i;

function stripRemindCommand(text: string): string {
  let result = text.trim();
  result = result.replace(REMIND_PREFIX, "");
  result = result.replace(REMIND_SUFFIX, " ");
  return result.trim();
}

function stripTemporal(text: string): string {
  let result = text;
  for (let i = 0; i < 8; i++) {
    const temporal = findTemporalExpression(result);
    if (!temporal) break;
    const before = result.slice(0, temporal.index).trim();
    const after = result.slice(temporal.index + temporal.length).trim();
    result = [before, after].filter(Boolean).join(" ").trim();
  }
  return result
    .replace(/\b(?:today|tomorrow|tonight)\b/gi, "")
    .replace(/\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

function toName(message: string): string {
  const trimmed = message.trim();
  if (!trimmed) return "Reminder";
  const firstSentence = trimmed.split(/[.!?]/)[0].trim();
  const candidate = firstSentence || trimmed;
  if (candidate.length <= 60) return candidate;
  return candidate.slice(0, 57).trimEnd() + "...";
}

export function extractReminderContent(text: string): { name: string; message: string } {
  let task = stripRemindCommand(text);
  task = stripTemporal(task);
  task = task.replace(/\s+/g, " ").trim();
  if (!task) {
    return { name: "Reminder", message: "Reminder" };
  }
  const message = task.charAt(0).toUpperCase() + task.slice(1);
  return { name: toName(message), message };
}

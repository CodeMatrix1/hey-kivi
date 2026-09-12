import { REMINDER_ACTIVE_WINDOW_MS } from "./reminderConstants";
import type { Reminder } from "../types";

export function isDue(reminder: Reminder, now: Date): boolean {
  return now.getTime() >= new Date(reminder.dueAt).getTime();
}

export function isWithinActiveWindow(reminder: Reminder, now: Date): boolean {
  const diff = new Date(reminder.dueAt).getTime() - now.getTime();
  return diff > 0 && diff <= REMINDER_ACTIVE_WINDOW_MS;
}

export function needsActiveRefresh(
  reminders: Reminder[],
  now: Date,
  firedIds?: Set<string>,
): boolean {
  return reminders.some((r) => {
    const diff = new Date(r.dueAt).getTime() - now.getTime();
    if (diff > 0 && diff <= REMINDER_ACTIVE_WINDOW_MS) return true;
    // Keep checking until due reminders have been toasted this session.
    if (diff <= 0 && firedIds && !firedIds.has(r.id)) return true;
    return false;
  });
}

export interface CheckRemindersResult {
  toasts: Reminder[];
  needsActiveRefresh: boolean;
}

export function checkReminders(
  now: Date,
  reminders: Reminder[],
  firedIds: Set<string>,
): CheckRemindersResult {
  const toasts: Reminder[] = [];
  for (const reminder of reminders) {
    if (isDue(reminder, now) && !firedIds.has(reminder.id)) {
      toasts.push(reminder);
    }
  }
  return {
    toasts,
    needsActiveRefresh: needsActiveRefresh(reminders, now, firedIds),
  };
}

import type { Reminder } from "../types";

const STORAGE_KEY = "kivi_reminders_v1";

function loadRaw(): Reminder[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Reminder[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveAll(reminders: Reminder[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(reminders));
}

export function listReminders(): Reminder[] {
  return loadRaw().sort(
    (a, b) => new Date(a.dueAt).getTime() - new Date(b.dueAt).getTime(),
  );
}

export function createReminder(
  input: Omit<Reminder, "id" | "createdAt"> & { id?: string; createdAt?: string },
): Reminder {
  const reminder: Reminder = {
    id: input.id || `rem_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name: input.name,
    message: input.message,
    dueAt: input.dueAt,
    createdAt: input.createdAt || new Date().toISOString(),
    sourceConversationId: input.sourceConversationId,
    sourceConversationTitle: input.sourceConversationTitle,
  };
  const all = loadRaw();
  all.push(reminder);
  saveAll(all);
  return reminder;
}

export function updateReminder(id: string, patch: Partial<Omit<Reminder, "id" | "createdAt">>): Reminder | null {
  const all = loadRaw();
  const idx = all.findIndex((r) => r.id === id);
  if (idx < 0) return null;
  all[idx] = { ...all[idx], ...patch };
  saveAll(all);
  return all[idx];
}

export function deleteReminder(id: string): boolean {
  const all = loadRaw();
  const next = all.filter((r) => r.id !== id);
  if (next.length === all.length) return false;
  saveAll(next);
  return true;
}

/** Test helper — clear all reminders. */
export function clearAllReminders(): void {
  localStorage.removeItem(STORAGE_KEY);
}

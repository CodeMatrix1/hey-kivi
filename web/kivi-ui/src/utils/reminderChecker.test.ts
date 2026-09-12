import { describe, expect, it } from "vitest";
import {
  REMINDER_ACTIVE_INTERVAL_MS,
  REMINDER_ACTIVE_WINDOW_MS,
} from "./reminderConstants";
import {
  checkReminders,
  isDue,
  isWithinActiveWindow,
  needsActiveRefresh,
} from "./reminderChecker";
import type { Reminder } from "../types";

function makeReminder(dueAt: Date, id = "r1"): Reminder {
  return {
    id,
    name: "Test",
    message: "Test message",
    dueAt: dueAt.toISOString(),
    createdAt: new Date().toISOString(),
  };
}

const now = new Date("2026-09-12T14:00:00");

describe("reminderChecker", () => {
  it("isDue when now >= dueAt", () => {
    const r = makeReminder(new Date("2026-09-12T13:00:00"));
    expect(isDue(r, now)).toBe(true);
  });

  it(">5 min away → no active refresh", () => {
    const r = makeReminder(new Date(now.getTime() + 6 * 60 * 1000));
    expect(needsActiveRefresh([r], now)).toBe(false);
  });

  it("exactly 5 min away → active refresh", () => {
    const r = makeReminder(new Date(now.getTime() + REMINDER_ACTIVE_WINDOW_MS));
    expect(isWithinActiveWindow(r, now)).toBe(true);
    expect(needsActiveRefresh([r], now)).toBe(true);
  });

  it("<5 min away → active refresh", () => {
    const r = makeReminder(new Date(now.getTime() + 3 * 60 * 1000));
    expect(needsActiveRefresh([r], now)).toBe(true);
  });

  it("active interval is 1 minute", () => {
    expect(REMINDER_ACTIVE_INTERVAL_MS).toBe(60 * 1000);
  });

  it("detects due reminders for toast", () => {
    const r = makeReminder(new Date("2026-09-12T13:00:00"));
    const result = checkReminders(now, [r], new Set());
    expect(result.toasts).toHaveLength(1);
  });

  it("firedIds prevents duplicate toast", () => {
    const r = makeReminder(new Date("2026-09-12T13:00:00"));
    const fired = new Set(["r1"]);
    const result = checkReminders(now, [r], fired);
    expect(result.toasts).toHaveLength(0);
  });

  it("past due still needs refresh until toasted", () => {
    const r = makeReminder(new Date("2026-09-12T13:00:00"));
    expect(needsActiveRefresh([r], now, new Set())).toBe(true);
    expect(needsActiveRefresh([r], now, new Set(["r1"]))).toBe(false);
  });
});

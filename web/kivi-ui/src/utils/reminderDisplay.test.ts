import { describe, expect, it } from "vitest";
import {
  containsSecondsUnit,
  formatCompactDue,
  formatExactDue,
  formatRelativeDue,
} from "./reminderDisplay";

const now = new Date("2026-09-12T14:00:00");

describe("formatCompactDue", () => {
  it("formats today with time", () => {
    const due = new Date("2026-09-12T20:44:00").toISOString();
    expect(formatCompactDue(due, now)).toMatch(/^Today · /);
  });
});

describe("formatExactDue", () => {
  it("shows today for same-day reminder", () => {
    const due = new Date("2026-09-12T21:00:00").toISOString();
    expect(formatExactDue(due, now)).toMatch(/today/i);
  });

  it("shows tomorrow for next-day reminder", () => {
    const due = new Date("2026-09-13T21:00:00").toISOString();
    expect(formatExactDue(due, now)).toMatch(/tomorrow/i);
  });

  it("shows weekday for later dates", () => {
    const due = new Date("2026-09-20T21:00:00").toISOString();
    const text = formatExactDue(due, now);
    expect(text).toMatch(/on \w+,/);
  });
});

describe("formatRelativeDue", () => {
  it("shows due when less than one minute", () => {
    const due = new Date(now.getTime() + 30 * 1000).toISOString();
    expect(formatRelativeDue(due, now)).toBe("due");
  });

  it("shows minutes", () => {
    const due = new Date(now.getTime() + 47 * 60 * 1000).toISOString();
    expect(formatRelativeDue(due, now)).toBe("in 47 minutes");
  });

  it("shows hours", () => {
    const due = new Date(now.getTime() + 8 * 60 * 60 * 1000).toISOString();
    expect(formatRelativeDue(due, now)).toBe("in 8 hours");
  });

  it("shows days", () => {
    const due = new Date(now.getTime() + 4 * 24 * 60 * 60 * 1000).toISOString();
    expect(formatRelativeDue(due, now)).toBe("in 4 days");
  });

  it("never contains seconds", () => {
    const cases = [
      new Date(now.getTime() + 30 * 1000),
      new Date(now.getTime() + 5 * 60 * 1000),
      new Date(now.getTime() + 2 * 60 * 60 * 1000),
    ];
    for (const d of cases) {
      const text = formatRelativeDue(d.toISOString(), now);
      expect(containsSecondsUnit(text)).toBe(false);
      expect(text).not.toMatch(/second/i);
    }
  });
});

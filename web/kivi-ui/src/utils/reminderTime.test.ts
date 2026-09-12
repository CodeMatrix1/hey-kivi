import { describe, expect, it } from "vitest";
import {
  findTemporalExpression,
  hasRecognizableDateTime,
  isDueAtInFuture,
  resolveDueAt,
} from "./reminderTime";

const now = new Date("2026-09-12T14:00:00");

describe("reminderTime", () => {
  it("detects tomorrow at time", () => {
    expect(hasRecognizableDateTime("tomorrow at 6 PM")).toBe(true);
    const due = resolveDueAt("Remind me tomorrow at 6 PM", now);
    expect(due).not.toBeNull();
    const d = new Date(due!);
    expect(d.getDate()).toBe(13);
    expect(d.getHours()).toBe(18);
  });

  it("today at passed time resolves to past", () => {
    const due = resolveDueAt("today at 9 AM", now);
    expect(due).not.toBeNull();
    expect(isDueAtInFuture(due!, now)).toBe(false);
  });

  it("in 2 hours resolves relative to now", () => {
    const due = resolveDueAt("in 2 hours", now);
    expect(due).not.toBeNull();
    const diff = new Date(due!).getTime() - now.getTime();
    expect(diff).toBe(2 * 60 * 60 * 1000);
  });

  it("in 30 minutes", () => {
    const due = resolveDueAt("in 30 minutes", now);
    const diff = new Date(due!).getTime() - now.getTime();
    expect(diff).toBe(30 * 60 * 1000);
  });

  it("in 3 days", () => {
    const due = resolveDueAt("in 3 days", now);
    const d = new Date(due!);
    expect(d.getDate()).toBe(15);
  });

  it("at explicit AM/PM", () => {
    const due = resolveDueAt("at 10:30 AM tomorrow", now);
    const d = new Date(due!);
    expect(d.getHours()).toBe(10);
    expect(d.getMinutes()).toBe(30);
  });

  it("on month day", () => {
    const due = resolveDueAt("on September 15 at 10 AM", now);
    expect(due).not.toBeNull();
    const d = new Date(due!);
    expect(d.getMonth()).toBe(8);
    expect(d.getDate()).toBe(15);
    expect(d.getHours()).toBe(10);
  });

  it("findTemporalExpression returns match", () => {
    const m = findTemporalExpression("Remind me in 5 hours please");
    expect(m).not.toBeNull();
    expect(m!.text.toLowerCase()).toContain("in 5 hours");
  });

  it("tonight resolves", () => {
    const due = resolveDueAt("tonight", now);
    expect(due).not.toBeNull();
  });

  it("resolves 8pm tomorrow without at", () => {
    const due = resolveDueAt("remind me about a call 8pm tomorrow", now);
    expect(due).not.toBeNull();
    const d = new Date(due!);
    expect(d.getDate()).toBe(13);
    expect(d.getHours()).toBe(20);
  });
});

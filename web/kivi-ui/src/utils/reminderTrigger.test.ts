import { describe, expect, it } from "vitest";
import { containsRemindKeyword, evaluateReminderTrigger } from "./reminderTrigger";

const now = new Date("2026-09-12T14:00:00");

describe("containsRemindKeyword", () => {
  it("detects remind case-insensitively", () => {
    expect(containsRemindKeyword("Remind me")).toBe(true);
    expect(containsRemindKeyword("please REMIND")).toBe(true);
  });

  it("rejects without remind", () => {
    expect(containsRemindKeyword("Call Rahul tomorrow")).toBe(false);
  });
});

describe("evaluateReminderTrigger", () => {
  it("valid future reminder triggers confirm", () => {
    const result = evaluateReminderTrigger(
      "Remind me to call Rahul tomorrow at 6 PM",
      now,
    );
    expect(result.kind).toBe("confirm");
    if (result.kind === "confirm") {
      expect(result.draft.name).toContain("Rahul");
      expect(new Date(result.draft.dueAt).getTime()).toBeGreaterThan(now.getTime());
    }
  });

  it("no remind → not_reminder", () => {
    expect(evaluateReminderTrigger("Call Rahul tomorrow", now).kind).toBe("not_reminder");
  });

  it("remind without date/time → not_reminder", () => {
    expect(evaluateReminderTrigger("Remind me to call Rahul", now).kind).toBe("not_reminder");
  });

  it("past time → not_reminder", () => {
    expect(
      evaluateReminderTrigger("Remind me to call Rahul at 9 AM", now).kind,
    ).toBe("not_reminder");
  });

  it("at 9 pm tonight triggers confirm when before 9pm", () => {
    const result = evaluateReminderTrigger(
      "remind me abt the payments review at 9 pm",
      now,
    );
    expect(result.kind).toBe("confirm");
  });

  it("relative future in 2 hours → confirm", () => {
    const result = evaluateReminderTrigger(
      "Can you remind me about the meeting in 2 hours?",
      now,
    );
    expect(result.kind).toBe("confirm");
  });

  it("dueAt exactly now does not trigger", () => {
    const exact = new Date(now);
    const text = "Remind me in 0 minutes to test";
    const result = evaluateReminderTrigger(text, exact);
    expect(result.kind).toBe("not_reminder");
  });
});

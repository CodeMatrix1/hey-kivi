import { describe, expect, it } from "vitest";
import { REMINDER_CONTENT_MAX_LENGTH } from "./reminderConstants";
import { parseReminderMessage, parseSuppliedReminderContent } from "./reminderFlow";

const now = new Date("2026-09-12T14:00:00");

describe("reminderFlow", () => {
  it("short valid message → confirm", () => {
    const result = parseReminderMessage(
      "Remind me to call Rahul tomorrow at 6 PM",
      now,
    );
    expect(result.kind).toBe("confirm");
  });

  it("long valid message → need_content", () => {
    const padding = "x".repeat(REMINDER_CONTENT_MAX_LENGTH);
    const result = parseReminderMessage(
      `Remind me to ${padding} tomorrow at 6 PM`,
      now,
    );
    expect(result.kind).toBe("need_content");
  });

  it("long message without valid trigger → not_reminder", () => {
    const padding = "x".repeat(REMINDER_CONTENT_MAX_LENGTH + 50);
    expect(parseReminderMessage(padding, now).kind).toBe("not_reminder");
  });

  it("supplied content after long flow → confirm", () => {
    const dueAt = new Date("2026-09-13T18:00:00").toISOString();
    const result = parseSuppliedReminderContent("Call Rahul about Slack", dueAt);
    expect(result.kind).toBe("confirm");
    if (result.kind === "confirm") {
      expect(result.draft.dueAt).toBe(dueAt);
      expect(result.draft.message).toContain("Rahul");
    }
  });
});

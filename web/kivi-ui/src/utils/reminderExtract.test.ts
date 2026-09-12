import { describe, expect, it } from "vitest";
import { extractReminderContent } from "./reminderExtract";

describe("extractReminderContent", () => {
  it("strips remind command and temporal phrase", () => {
    const { name, message } = extractReminderContent(
      "Remind me to call Rahul tomorrow at 6 PM",
    );
    expect(name).toBe("Call Rahul");
    expect(message).toBe("Call Rahul");
  });

  it("handles remind me about", () => {
    const { message } = extractReminderContent(
      "Remind me about the Slack integration in 2 hours",
    );
    expect(message.toLowerCase()).toContain("slack");
  });

  it("handles abt abbreviation", () => {
    const { message } = extractReminderContent(
      "remind me abt the payments review at 9 pm",
    );
    expect(message.toLowerCase()).toContain("payments review");
  });

  it("strips bare time and day without at", () => {
    const { name } = extractReminderContent("remind me about a call 8pm tomorrow");
    expect(name.toLowerCase()).toBe("a call");
  });
});

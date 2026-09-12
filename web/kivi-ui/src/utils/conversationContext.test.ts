import { describe, expect, it } from "vitest";
import { buildChatContext } from "./conversationContext";
import type { StoredMessage } from "../types";

function msg(role: "user" | "assistant", text: string, id: string): StoredMessage {
  return { id, role, text, at: new Date().toISOString() };
}

describe("buildChatContext", () => {
  it("returns empty for no messages", () => {
    expect(buildChatContext([])).toEqual([]);
  });

  it("returns one turn when one pair exists", () => {
    const messages = [
      msg("user", "Hi", "1"),
      msg("assistant", "Hello", "2"),
    ];
    expect(buildChatContext(messages)).toEqual([
      { role: "user", content: "Hi" },
      { role: "assistant", content: "Hello" },
    ]);
  });

  it("returns up to 3 turns oldest-first", () => {
    const messages = [
      msg("user", "A1", "1"),
      msg("assistant", "A2", "2"),
      msg("user", "B1", "3"),
      msg("assistant", "B2", "4"),
      msg("user", "C1", "5"),
      msg("assistant", "C2", "6"),
      msg("user", "D1", "7"),
      msg("assistant", "D2", "8"),
    ];
    const ctx = buildChatContext(messages);
    expect(ctx).toHaveLength(6);
    expect(ctx[0].content).toBe("B1");
    expect(ctx[5].content).toBe("D2");
  });

  it("ignores orphan assistant without user", () => {
    const messages = [msg("assistant", "solo", "1")];
    expect(buildChatContext(messages)).toEqual([]);
  });

  it("handles partial trailing user without assistant", () => {
    const messages = [
      msg("user", "A1", "1"),
      msg("assistant", "A2", "2"),
      msg("user", "B1", "3"),
    ];
    const ctx = buildChatContext(messages);
    expect(ctx).toHaveLength(2);
    expect(ctx[0].content).toBe("A1");
  });
});

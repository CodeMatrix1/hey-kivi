import { describe, expect, it } from "vitest";
import { groupConversations, polishConversationTitle } from "./conversationDisplay";
import type { Conversation } from "../types";

function conv(id: string, title: string, lastUsedAt: string): Conversation {
  return {
    id,
    title,
    createdAt: lastUsedAt,
    updatedAt: lastUsedAt,
    lastUsedAt,
    messages: [],
  };
}

describe("polishConversationTitle", () => {
  it("maps common demo titles to curated labels", () => {
    expect(polishConversationTitle("remind me abt the paymen…")).toBe("Payment review");
    expect(polishConversationTitle("What have I said about ho…")).toBe("Family locations");
    expect(polishConversationTitle("How should you spell my n…")).toBe("Name spelling");
  });

  it("leaves new chat unchanged", () => {
    expect(polishConversationTitle("New chat")).toBe("New chat");
  });
});

describe("groupConversations", () => {
  const now = new Date("2026-09-12T14:00:00");

  it("groups into Today and Earlier", () => {
    const groups = groupConversations(
      [
        conv("1", "A", "2026-09-12T10:00:00.000Z"),
        conv("2", "B", "2026-09-11T10:00:00.000Z"),
      ],
      now,
    );
    expect(groups.map((g) => g.label)).toEqual(["Today", "Earlier"]);
    expect(groups[0].conversations).toHaveLength(1);
    expect(groups[1].conversations).toHaveLength(1);
  });
});

import { describe, expect, it } from "vitest";
import {
  DEMO_CHATS_SEED_VERSION_KEY,
  importDemoChats,
  parseDemoChatsFile,
} from "./demoChats";
import { CONVERSATIONS_STORAGE_KEY } from "./conversations";
import { TOPICS_STORAGE_KEY } from "./topics";

describe("parseDemoChatsFile", () => {
  it("parses a valid conversation", () => {
    const file = parseDemoChatsFile({
      version: 1,
      conversations: [
        {
          id: "conv_a",
          title: "Test chat",
          createdAt: "2026-09-01T10:00:00.000Z",
          updatedAt: "2026-09-01T10:01:00.000Z",
          messages: [
            {
              id: "m1",
              role: "user",
              text: "hello",
              at: "2026-09-01T10:00:00.000Z",
            },
            {
              id: "m2",
              role: "assistant",
              text: "hi there",
              at: "2026-09-01T10:01:00.000Z",
              trace: { decision: "answer", tools_used: ["general_chat"] },
            },
          ],
        },
      ],
    });
    expect(file.version).toBe(1);
    expect(file.conversations).toHaveLength(1);
    expect(file.conversations[0].messages).toHaveLength(2);
  });

  it("parses optional topics", () => {
    const file = parseDemoChatsFile({
      version: 2,
      conversations: [
        {
          id: "conv_a",
          title: "Chat",
          createdAt: "2026-09-01T10:00:00.000Z",
          updatedAt: "2026-09-01T10:00:00.000Z",
          messages: [
            { id: "m1", role: "user", text: "hello", at: "2026-09-01T10:00:00.000Z" },
          ],
        },
      ],
      topics: [
        {
          id: "topic_a",
          name: "Slack",
          createdAt: "2026-09-01T10:00:00.000Z",
          updatedAt: "2026-09-01T10:00:00.000Z",
          conversationIds: ["conv_a"],
          notes: [
            {
              id: "n1",
              text: "Use webhooks",
              type: "decision",
              sourceConversationId: "conv_a",
              sourceMessageId: "m1",
              createdAt: "2026-09-01T10:00:00.000Z",
              updatedAt: "2026-09-01T10:00:00.000Z",
            },
          ],
        },
      ],
    });
    expect(file.topics).toHaveLength(1);
    expect(file.topics?.[0].notes[0].type).toBe("decision");
  });

  it("rejects duplicate conversation ids", () => {
    expect(() =>
      parseDemoChatsFile({
        version: 1,
        conversations: [
          {
            id: "conv_dup",
            title: "One",
            createdAt: "2026-09-01T10:00:00.000Z",
            updatedAt: "2026-09-01T10:00:00.000Z",
            messages: [
              { id: "m1", role: "user", text: "a", at: "2026-09-01T10:00:00.000Z" },
            ],
          },
          {
            id: "conv_dup",
            title: "Two",
            createdAt: "2026-09-01T11:00:00.000Z",
            updatedAt: "2026-09-01T11:00:00.000Z",
            messages: [
              { id: "m2", role: "user", text: "b", at: "2026-09-01T11:00:00.000Z" },
            ],
          },
        ],
      }),
    ).toThrow(/duplicate conversation id/);
  });
});

describe("importDemoChats", () => {
  it("replace_empty imports only when storage is empty", () => {
    localStorage.clear();
    const payload = parseDemoChatsFile({
      version: 2,
      conversations: [
        {
          id: "conv_seed",
          title: "Seeded",
          createdAt: "2026-09-01T10:00:00.000Z",
          updatedAt: "2026-09-01T10:00:00.000Z",
          messages: [
            { id: "m1", role: "user", text: "seed", at: "2026-09-01T10:00:00.000Z" },
          ],
        },
      ],
    });
    const first = importDemoChats(payload, "replace_empty");
    expect(first.imported).toBe(1);
    expect(localStorage.getItem(DEMO_CHATS_SEED_VERSION_KEY)).toBe("2");

    const second = importDemoChats(payload, "replace_empty");
    expect(second.imported).toBe(0);
    expect(second.skipped).toBe(1);
  });

  it("merge skips existing ids", () => {
    localStorage.clear();
    localStorage.setItem(
      CONVERSATIONS_STORAGE_KEY,
      JSON.stringify([
        {
          id: "conv_existing",
          title: "Existing",
          createdAt: "2026-09-01T09:00:00.000Z",
          updatedAt: "2026-09-01T09:00:00.000Z",
          messages: [
            { id: "m0", role: "user", text: "old", at: "2026-09-01T09:00:00.000Z" },
          ],
        },
      ]),
    );
    const payload = parseDemoChatsFile({
      version: 3,
      conversations: [
        {
          id: "conv_existing",
          title: "Should skip",
          createdAt: "2026-09-01T10:00:00.000Z",
          updatedAt: "2026-09-01T10:00:00.000Z",
          messages: [
            { id: "m1", role: "user", text: "new", at: "2026-09-01T10:00:00.000Z" },
          ],
        },
        {
          id: "conv_new",
          title: "New",
          createdAt: "2026-09-01T11:00:00.000Z",
          updatedAt: "2026-09-01T11:00:00.000Z",
          messages: [
            { id: "m2", role: "user", text: "added", at: "2026-09-01T11:00:00.000Z" },
          ],
        },
      ],
    });
    const result = importDemoChats(payload, "merge");
    expect(result.imported).toBe(1);
    expect(result.skipped).toBe(1);
    expect(result.total).toBe(2);
    const stored = JSON.parse(localStorage.getItem(CONVERSATIONS_STORAGE_KEY) || "[]");
    expect(stored.find((c: { id: string }) => c.id === "conv_existing")?.title).toBe(
      "Existing",
    );
  });

  it("replace_empty imports topics when topic storage is empty", () => {
    localStorage.clear();
    const payload = parseDemoChatsFile({
      version: 2,
      conversations: [
        {
          id: "conv_seed",
          title: "Seeded",
          createdAt: "2026-09-01T10:00:00.000Z",
          updatedAt: "2026-09-01T10:00:00.000Z",
          messages: [
            { id: "m1", role: "user", text: "seed", at: "2026-09-01T10:00:00.000Z" },
          ],
        },
      ],
      topics: [
        {
          id: "topic_seed",
          name: "Slack",
          createdAt: "2026-09-01T10:00:00.000Z",
          updatedAt: "2026-09-01T10:00:00.000Z",
          conversationIds: ["conv_seed"],
          notes: [
            {
              id: "n1",
              text: "Use webhooks",
              type: "decision",
              createdAt: "2026-09-01T10:00:00.000Z",
              updatedAt: "2026-09-01T10:00:00.000Z",
            },
          ],
        },
      ],
    });
    const result = importDemoChats(payload, "replace_empty");
    expect(result.topicsImported).toBe(1);
    const topics = JSON.parse(localStorage.getItem(TOPICS_STORAGE_KEY) || "[]");
    expect(topics[0].name).toBe("Slack");
  });
});

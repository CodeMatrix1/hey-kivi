import { beforeEach, describe, expect, it } from "vitest";
import {
  addManualNote,
  addNote,
  clearAllTopics,
  createTopic,
  getTopic,
  linkConversation,
  listTopics,
  saveNoteAndLinkConversation,
  deleteTopic,
  updateNote,
  updateTopicName,
} from "./topics";

beforeEach(() => {
  clearAllTopics();
});

describe("topics storage", () => {
  it("creates empty topic", () => {
    const topic = createTopic("Slack");
    expect(topic.name).toBe("Slack");
    expect(topic.notes).toEqual([]);
    expect(topic.conversationIds).toEqual([]);
    expect(listTopics()[0].id).toBe(topic.id);
  });

  it("rejects empty topic name", () => {
    expect(() => createTopic("  ")).toThrow();
  });

  it("adds note with required source refs and links conversation", () => {
    const topic = createTopic("Goa Trip");
    const note = saveNoteAndLinkConversation(topic.id, {
      text: "Prefer slower pace trips.",
      type: "context",
      sourceConversationId: "conv_1",
      sourceMessageId: "msg_1",
      sourceConversationTitle: "Goa planning",
    });
    const updated = getTopic(topic.id);
    expect(updated?.notes[0].id).toBe(note.id);
    expect(updated?.conversationIds).toEqual(["conv_1"]);
  });

  it("requires source ids for notes", () => {
    const topic = createTopic("Job Search");
    expect(() =>
      addNote(topic.id, {
        text: "Note",
        type: "open",
        sourceConversationId: "",
        sourceMessageId: "msg_1",
      }),
    ).toThrow();
  });

  it("linkConversation does not duplicate ids", () => {
    const topic = createTopic("Slack");
    linkConversation(topic.id, "conv_a");
    linkConversation(topic.id, "conv_a");
    expect(getTopic(topic.id)?.conversationIds).toEqual(["conv_a"]);
  });

  it("updates topic name", () => {
    const topic = createTopic("Old name");
    updateTopicName(topic.id, "New name");
    expect(getTopic(topic.id)?.name).toBe("New name");
  });

  it("adds manual note without source refs", () => {
    const topic = createTopic("Planning");
    const note = addManualNote(topic.id, {
      text: "Prefer async updates.",
      type: "decision",
    });
    const updated = getTopic(topic.id);
    expect(updated?.notes[0].id).toBe(note.id);
    expect(updated?.notes[0].sourceConversationId).toBeUndefined();
    expect(updated?.conversationIds).toEqual([]);
  });

  it("deletes topic", () => {
    const topic = createTopic("Temporary");
    expect(deleteTopic(topic.id)).toBe(true);
    expect(getTopic(topic.id)).toBeUndefined();
  });

  it("updates note text and type", () => {
    const topic = createTopic("Job Search");
    const note = addManualNote(topic.id, { text: "Draft", type: "open" });
    updateNote(topic.id, note.id, { text: "Final", type: "decision" });
    const updated = getTopic(topic.id)?.notes[0];
    expect(updated?.text).toBe("Final");
    expect(updated?.type).toBe("decision");
  });
});

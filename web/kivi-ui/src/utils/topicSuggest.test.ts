import { beforeEach, describe, expect, it } from "vitest";
import { clearAllTopics, createTopic } from "../storage/topics";
import {
  canShowAutoPrompt,
  clearSuggestState,
  recordPromptDismissed,
  recordPromptShown,
} from "../storage/topicSuggestState";
import { maybeAutoSuggestTopicNotes } from "./topicSuggest";

beforeEach(() => {
  clearAllTopics();
  clearSuggestState();
});

describe("topicSuggest", () => {
  it("suggests when topic name and durable signal present", () => {
    const topic = createTopic("Slack");
    const result = maybeAutoSuggestTopicNotes({
      conversationId: "conv_1",
      messageId: "msg_1",
      messageText:
        "For the Slack integration we decided to use webhooks instead of polling.",
      topics: [topic],
    });
    expect(result?.topicId).toBe(topic.id);
    expect(result?.drafts[0].text).toContain("webhooks");
  });

  it("does not suggest on greeting alone", () => {
    const topic = createTopic("Slack");
    const result = maybeAutoSuggestTopicNotes({
      conversationId: "conv_1",
      messageId: "msg_1",
      messageText: "Hi Slack team, thanks!",
      topics: [topic],
    });
    expect(result).toBeNull();
  });

  it("suggests open questions that mention the topic", () => {
    const topic = createTopic("Slack integration");
    const result = maybeAutoSuggestTopicNotes({
      conversationId: "conv_1",
      messageId: "msg_open",
      messageText:
        "some thing is faulty is that right in slack integration",
      topics: [topic],
    });
    expect(result?.topicId).toBe(topic.id);
    expect(result?.drafts[0].type).toBe("open");
  });

  it("does not suggest when topic name missing from message", () => {
    const topics = [createTopic("Slack")];
    const result = maybeAutoSuggestTopicNotes({
      conversationId: "conv_1",
      messageId: "msg_1",
      messageText: "We decided to use webhooks instead of polling for the integration.",
      topics,
    });
    expect(result).toBeNull();
  });

  it("enforces max 2 displayed prompts per conversation", () => {
    const convId = "conv_spam";
    expect(canShowAutoPrompt(convId, "t1", "m1")).toBe(true);
    recordPromptShown(convId, "m1");
    recordPromptShown(convId, "m2");
    expect(canShowAutoPrompt(convId, "t2", "m3")).toBe(false);
  });

  it("suppresses rejected topic for conversation", () => {
    const convId = "conv_reject";
    recordPromptShown(convId, "m1");
    recordPromptDismissed(convId, "topic_slack");
    expect(canShowAutoPrompt(convId, "topic_slack", "m2")).toBe(false);
  });
});

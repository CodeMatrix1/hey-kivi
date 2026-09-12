import { useEffect, useRef, useState } from "react";
import { postChat } from "../api/client";
import {
  appendMessage,
  buildApiMessage,
  createConversation,
  getConversation,
  pushLearningFromTrace,
} from "../storage/conversations";
import { createReminder } from "../storage/reminders";
import {
  recordPromptDismissed,
  recordPromptShown,
} from "../storage/topicSuggestState";
import {
  createTopic,
  getTopic,
  listTopics,
  saveNoteAndLinkConversation,
  updateTopicName,
} from "../storage/topics";
import type {
  Conversation,
  Dictation,
  PendingDictationContext,
  ReminderDraft,
  StoredMessage,
  Topic,
} from "../types";
import { buildChatContext } from "../utils/conversationContext";
import { friendlyChatError, INTERRUPTED_RESPONSE_MESSAGE } from "../utils/errors";
import {
  LONG_MESSAGE_CONTENT_PROMPT,
  REMINDER_REJECTED_MESSAGE,
  REMINDER_SAVED_MESSAGE,
  parseReminderMessage,
  parseSuppliedReminderContent,
} from "../utils/reminderFlow";
import { classifyNoteType, proposeNoteFromMessage } from "../utils/topicNotes";
import { maybeAutoSuggestTopicNotes } from "../utils/topicSuggest";
import { FromHistoryBlock } from "./FromHistoryBlock";
import { WelcomeIntro } from "./WelcomeIntro";
import { PersonalizedBadge } from "./PersonalizedBadge";
import { ReminderConfirmCard } from "./ReminderConfirmCard";
import {
  ReminderForm,
  dueAtToFormValues,
  formValuesToDueAt,
  type ReminderFormValues,
} from "./ReminderForm";
import {
  TopicNoteApprovalCard,
  type TopicNoteApprovalItem,
} from "./TopicNoteApprovalCard";
import { UserMessageMenu } from "./UserMessageMenu";

type ReminderChatState =
  | { mode: "idle" }
  | { mode: "awaiting_content"; dueAt: string }
  | { mode: "confirming"; draft: ReminderDraft }
  | { mode: "editing"; draft: ReminderDraft };

type TopicApprovalState =
  | { mode: "idle" }
  | {
      mode: "approving";
      topicId: string;
      topicName: string;
      source: "manual" | "auto";
      items: TopicNoteApprovalItem[];
    };

interface ChatViewProps {
  userId: string;
  conversationId: string | null;
  conversations: Conversation[];
  topics: Topic[];
  dictations: Dictation[];
  prefill?: string;
  pendingDictation?: PendingDictationContext | null;
  scrollToMessageId?: string | null;
  onConversationCreated: (id: string) => void;
  onConversationUpdated: () => void;
  onTopicsUpdated: () => void;
  onPendingDictationConsumed: () => void;
  onViewInHistory?: (dictationId: string) => void;
  onScrollToMessageConsumed?: () => void;
  onReminderCreated?: () => void;
}

export function ChatView({
  userId,
  conversationId,
  conversations,
  topics,
  dictations,
  prefill,
  pendingDictation,
  scrollToMessageId,
  onConversationCreated,
  onConversationUpdated,
  onTopicsUpdated,
  onPendingDictationConsumed,
  onViewInHistory,
  onScrollToMessageConsumed,
  onReminderCreated,
}: ChatViewProps) {
  const [input, setInput] = useState(prefill || "");
  const [busy, setBusy] = useState(false);
  const [turnErrors, setTurnErrors] = useState<Record<string, string>>({});
  const [reminderState, setReminderState] = useState<ReminderChatState>({ mode: "idle" });
  const [topicApproval, setTopicApproval] = useState<TopicApprovalState>({ mode: "idle" });
  const [openMenuMessageId, setOpenMenuMessageId] = useState<string | null>(null);
  const [highlightMessageId, setHighlightMessageId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const prevConvIdRef = useRef<string | null>(conversationId);
  const topicApprovalRef = useRef(topicApproval);

  useEffect(() => {
    topicApprovalRef.current = topicApproval;
  }, [topicApproval]);

  const activeConvId = conversationId ?? prevConvIdRef.current;
  const conv =
    (activeConvId
      ? conversations.find((c) => c.id === activeConvId) ?? getConversation(activeConvId)
      : null) ?? null;

  useEffect(() => {
    if (prefill !== undefined) setInput(prefill);
  }, [prefill]);

  useEffect(() => {
    const prev = prevConvIdRef.current;
    if (prev === conversationId) return;
    prevConvIdRef.current = conversationId;
    if (prev === null && conversationId !== null) return;
    setTurnErrors({});
    setReminderState({ mode: "idle" });
    setTopicApproval({ mode: "idle" });
    setOpenMenuMessageId(null);
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [
    conv?.messages.length,
    busy,
    Object.keys(turnErrors).length,
    reminderState.mode,
    topicApproval.mode,
  ]);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  useEffect(() => {
    if (!scrollToMessageId) return;
    const el = document.querySelector(`[data-message-id="${scrollToMessageId}"]`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      setHighlightMessageId(scrollToMessageId);
      const timer = window.setTimeout(() => {
        setHighlightMessageId(null);
        onScrollToMessageConsumed?.();
      }, 2000);
      return () => window.clearTimeout(timer);
    }
    onScrollToMessageConsumed?.();
  }, [scrollToMessageId, conv?.messages.length, onScrollToMessageConsumed]);

  function markTurnFailed(userMessageId: string, message: string) {
    setTurnErrors((prev) => ({ ...prev, [userMessageId]: message }));
  }

  function stopResponse(pendingUserMessageId: string | null) {
    abortRef.current?.abort();
    abortRef.current = null;
    setBusy(false);
    if (pendingUserMessageId) {
      markTurnFailed(pendingUserMessageId, INTERRUPTED_RESPONSE_MESSAGE);
    }
  }

  function appendLocalAssistant(convId: string, text: string) {
    const botMsg: StoredMessage = {
      id: `msg_${Date.now()}_a`,
      role: "assistant",
      text,
      at: new Date().toISOString(),
    };
    appendMessage(convId, botMsg);
    onConversationUpdated();
  }

  function ensureConversation(): string {
    if (conversationId) return conversationId;
    const created = createConversation();
    prevConvIdRef.current = created.id;
    onConversationCreated(created.id);
    return created.id;
  }

  function conversationTitle(convId: string): string {
    return (
      conversations.find((c) => c.id === convId)?.title ??
      getConversation(convId)?.title ??
      "Conversation"
    );
  }

  function openTopicApproval(
    topicId: string,
    message: StoredMessage,
    source: "manual" | "auto",
  ) {
    const topic = getTopic(topicId) ?? topics.find((t) => t.id === topicId);
    if (!topic || !activeConvId) return;
    const proposed = proposeNoteFromMessage(message.text);
    setTopicApproval({
      mode: "approving",
      topicId,
      topicName: topic.name,
      source,
      items: [
        {
          text: proposed,
          type: classifyNoteType(message.text),
          sourceConversationId: activeConvId,
          sourceMessageId: message.id,
          sourceConversationTitle: conversationTitle(activeConvId),
          sourceMessageText: message.text,
          selected: true,
        },
      ],
    });
    setOpenMenuMessageId(null);
    if (source === "auto") {
      recordPromptShown(activeConvId, message.id);
    }
  }

  function tryAutoSuggest(convId: string, userMsg: StoredMessage) {
    const freshTopics = listTopics();
    const suggestion = maybeAutoSuggestTopicNotes({
      conversationId: convId,
      messageId: userMsg.id,
      messageText: userMsg.text,
      topics: freshTopics,
    });
    if (!suggestion) return;
    setTopicApproval({
      mode: "approving",
      topicId: suggestion.topicId,
      topicName: suggestion.topicName,
      source: "auto",
      items: suggestion.drafts.map((draft) => ({
        ...draft,
        sourceConversationTitle: conversationTitle(convId),
        selected: true,
      })),
    });
    recordPromptShown(convId, userMsg.id);
  }

  function handleAcceptTopicNotes() {
    if (topicApproval.mode !== "approving" || !activeConvId) return;
    const { topicId, topicName, items, source } = topicApproval;
    const original = getTopic(topicId);
    const trimmedName = topicName.trim();
    if (original && trimmedName && original.name !== trimmedName) {
      updateTopicName(topicId, trimmedName);
    }
    for (const item of items.filter((i) => i.selected && i.text.trim())) {
      saveNoteAndLinkConversation(topicId, {
        text: item.text.trim(),
        type: item.type,
        sourceConversationId: item.sourceConversationId,
        sourceMessageId: item.sourceMessageId,
        sourceConversationTitle: item.sourceConversationTitle,
      });
    }
    setTopicApproval({ mode: "idle" });
    onTopicsUpdated();
    if (source === "auto") {
      appendLocalAssistant(activeConvId, "Added to your topic.");
    }
  }

  function handleRejectTopicApproval() {
    if (topicApproval.mode !== "approving" || !activeConvId) {
      setTopicApproval({ mode: "idle" });
      return;
    }
    if (topicApproval.source === "auto") {
      recordPromptDismissed(activeConvId, topicApproval.topicId);
    }
    setTopicApproval({ mode: "idle" });
  }

  function handleManualSelectTopic(topicId: string, message: StoredMessage) {
    openTopicApproval(topicId, message, "manual");
  }

  function handleCreateTopicForMessage(message: StoredMessage) {
    const name = window.prompt("Topic name");
    if (!name?.trim()) return;
    try {
      const topic = createTopic(name);
      onTopicsUpdated();
      openTopicApproval(topic.id, message, "manual");
    } catch {
      // ignore empty name
    }
  }

  function withSource(draft: ReminderDraft, convId: string | null): ReminderDraft {
    const c = convId ? conversations.find((x) => x.id === convId) ?? getConversation(convId) : null;
    return {
      ...draft,
      sourceConversationId: convId || undefined,
      sourceConversationTitle: c?.title,
    };
  }

  function handleAcceptReminder(draft: ReminderDraft, convId: string | null) {
    const enriched = withSource(draft, convId);
    createReminder({
      name: enriched.name,
      message: enriched.message,
      dueAt: enriched.dueAt,
      sourceConversationId: enriched.sourceConversationId,
      sourceConversationTitle: enriched.sourceConversationTitle,
    });
    setReminderState({ mode: "idle" });
    onReminderCreated?.();
    if (convId) {
      appendLocalAssistant(convId, REMINDER_SAVED_MESSAGE);
    }
  }

  function handleRejectReminder(convId: string | null) {
    setReminderState({ mode: "idle" });
    if (convId) {
      appendLocalAssistant(convId, REMINDER_REJECTED_MESSAGE);
    }
  }

  async function handleContinueChat(convId: string | null) {
    setReminderState({ mode: "idle" });
    if (!convId || busy) return;

    const msgs = conv?.messages ?? getConversation(convId)?.messages ?? [];
    const lastUser = [...msgs].reverse().find((m) => m.role === "user");
    if (!lastUser) return;

    await sendNormalChat(convId, lastUser.text, lastUser);
  }

  async function sendNormalChat(convId: string, trimmed: string, userMsg: StoredMessage) {
    const dictationQuote = pendingDictation?.formatted || pendingDictation?.asr;
    const apiMessage = buildApiMessage(trimmed, dictationQuote);
    const priorMessages = conv?.messages ?? [];
    const context = buildChatContext(priorMessages);

    setBusy(true);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const data = await postChat(userId, apiMessage, { context, signal: controller.signal });
      const botMsg: StoredMessage = {
        id: `msg_${Date.now()}_a`,
        role: "assistant",
        text: data.reply,
        trace: data.trace,
        metrics: data.metrics,
        at: new Date().toISOString(),
      };
      appendMessage(convId, botMsg);
      pushLearningFromTrace(data.trace);
      onConversationUpdated();
      if (pendingDictation) onPendingDictationConsumed();
    } catch (err) {
      markTurnFailed(userMsg.id, friendlyChatError(err));
    } finally {
      abortRef.current = null;
      setBusy(false);
      if (topicApprovalRef.current.mode === "idle") {
        tryAutoSuggest(convId, userMsg);
      }
    }
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setInput("");

    const convId = ensureConversation();

    const userMsg: StoredMessage = {
      id: `msg_${Date.now()}_u`,
      role: "user",
      text: trimmed,
      at: new Date().toISOString(),
    };
    appendMessage(convId, userMsg);
    onConversationUpdated();
    setTurnErrors((prev) => {
      const next = { ...prev };
      delete next[userMsg.id];
      return next;
    });

    if (reminderState.mode === "awaiting_content") {
      const result = parseSuppliedReminderContent(trimmed, reminderState.dueAt);
      if (result.kind === "confirm") {
        setReminderState({ mode: "confirming", draft: result.draft });
      }
      return;
    }

    const parseResult = parseReminderMessage(trimmed);
    if (parseResult.kind === "need_content") {
      setReminderState({ mode: "awaiting_content", dueAt: parseResult.dueAt });
      appendLocalAssistant(convId, LONG_MESSAGE_CONTENT_PROMPT);
      return;
    }
    if (parseResult.kind === "confirm") {
      setReminderState({ mode: "confirming", draft: parseResult.draft });
      return;
    }

    await sendNormalChat(convId, trimmed, userMsg);
  }

  const messages = conv?.messages ?? [];
  const confirmingDraft =
    reminderState.mode === "confirming" ? reminderState.draft : null;
  const editingDraft = reminderState.mode === "editing" ? reminderState.draft : null;
  const approvingTopic = topicApproval.mode === "approving" ? topicApproval : null;
  const showEmpty =
    messages.length === 0 &&
    !busy &&
    reminderState.mode === "idle" &&
    topicApproval.mode === "idle" &&
    !confirmingDraft &&
    !editingDraft;
  const pendingUserMessageId =
    busy && messages.length > 0 && messages[messages.length - 1].role === "user"
      ? messages[messages.length - 1].id
      : null;

  return (
    <div className="chat-view">
      {showEmpty ? (
        <div className="empty-state">
          <WelcomeIntro />
        </div>
      ) : (
        <div className="messages">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`message-turn ${highlightMessageId === m.id ? "message-highlight" : ""}`}
              data-message-id={m.id}
            >
              <div className={`message message-${m.role}`}>
                {m.role === "user" && (
                  <UserMessageMenu
                    topics={topics}
                    open={openMenuMessageId === m.id}
                    onToggle={() =>
                      setOpenMenuMessageId((id) => (id === m.id ? null : m.id))
                    }
                    onSelectTopic={(topicId) => handleManualSelectTopic(topicId, m)}
                    onCreateTopic={() => handleCreateTopicForMessage(m)}
                  />
                )}
                <div className="message-bubble message-plain">{m.text}</div>
                {m.role === "assistant" && <PersonalizedBadge trace={m.trace} />}
              </div>
              {m.role === "assistant" && (
                <FromHistoryBlock
                  trace={m.trace}
                  dictations={dictations}
                  onViewInHistory={onViewInHistory}
                />
              )}
              {m.role === "user" && turnErrors[m.id] && (
                <div className="message message-assistant message-failed" role="alert">
                  <div className="message-bubble message-error">{turnErrors[m.id]}</div>
                </div>
              )}
            </div>
          ))}
          {busy && (
            <div className="message message-assistant">
              <div className="message-bubble typing">Kivi is thinking…</div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}

      {approvingTopic && (
        <div className="chat-reminder-panel">
          <TopicNoteApprovalCard
            topicName={approvingTopic.topicName}
            items={approvingTopic.items}
            mode={approvingTopic.source}
            onChangeItem={(index, patch) => {
              setTopicApproval((prev) => {
                if (prev.mode !== "approving") return prev;
                const items = prev.items.map((item, i) =>
                  i === index ? { ...item, ...patch } : item,
                );
                return { ...prev, items };
              });
            }}
            onToggleItem={(index) => {
              setTopicApproval((prev) => {
                if (prev.mode !== "approving") return prev;
                const items = prev.items.map((item, i) =>
                  i === index ? { ...item, selected: !item.selected } : item,
                );
                return { ...prev, items };
              });
            }}
            onTopicNameChange={(name) => {
              setTopicApproval((prev) => {
                if (prev.mode !== "approving") return prev;
                return { ...prev, topicName: name };
              });
            }}
            onAccept={handleAcceptTopicNotes}
            onReject={handleRejectTopicApproval}
          />
        </div>
      )}

      {editingDraft && (
        <div className="reminder-form-panel chat-reminder-panel">
          <ReminderForm
            initial={dueAtToFormValues(
              editingDraft.dueAt,
              editingDraft.name,
              editingDraft.message,
            )}
            submitLabel="Save"
            onSubmit={(values: ReminderFormValues) => {
              setReminderState({
                mode: "confirming",
                draft: {
                  ...editingDraft,
                  name: values.name.trim(),
                  message: values.message.trim(),
                  dueAt: formValuesToDueAt(values),
                },
              });
            }}
            onCancel={() =>
              setReminderState({ mode: "confirming", draft: editingDraft })
            }
          />
        </div>
      )}

      {confirmingDraft && !editingDraft && (
        <div className="chat-reminder-panel">
          <ReminderConfirmCard
            draft={confirmingDraft}
            onAccept={() => handleAcceptReminder(confirmingDraft, activeConvId)}
            onReject={() => handleRejectReminder(activeConvId)}
            onEdit={() => setReminderState({ mode: "editing", draft: confirmingDraft })}
            onContinueChat={() => handleContinueChat(activeConvId)}
          />
        </div>
      )}

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          if (busy) return;
          sendMessage(input);
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Message Kivi…"
          rows={2}
          disabled={busy}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (!busy) sendMessage(input);
            }
          }}
        />
        {busy ? (
          <button
            type="button"
            className="btn-stop"
            onClick={() => stopResponse(pendingUserMessageId)}
          >
            Stop
          </button>
        ) : (
          <button type="submit" className="btn-primary" disabled={!input.trim()}>
            Send
          </button>
        )}
      </form>
    </div>
  );
}

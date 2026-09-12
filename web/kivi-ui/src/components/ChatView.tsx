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
import type {
  Conversation,
  Dictation,
  PendingDictationContext,
  ReminderDraft,
  StoredMessage,
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

type ReminderChatState =
  | { mode: "idle" }
  | { mode: "awaiting_content"; dueAt: string }
  | { mode: "confirming"; draft: ReminderDraft }
  | { mode: "editing"; draft: ReminderDraft };

interface ChatViewProps {
  userId: string;
  conversationId: string | null;
  conversations: Conversation[];
  dictations: Dictation[];
  prefill?: string;
  pendingDictation?: PendingDictationContext | null;
  onConversationCreated: (id: string) => void;
  onConversationUpdated: () => void;
  onPendingDictationConsumed: () => void;
  onViewInHistory?: (dictationId: string) => void;
  onReminderCreated?: () => void;
}

export function ChatView({
  userId,
  conversationId,
  conversations,
  dictations,
  prefill,
  pendingDictation,
  onConversationCreated,
  onConversationUpdated,
  onPendingDictationConsumed,
  onViewInHistory,
  onReminderCreated,
}: ChatViewProps) {
  const [input, setInput] = useState(prefill || "");
  const [busy, setBusy] = useState(false);
  const [turnErrors, setTurnErrors] = useState<Record<string, string>>({});
  const [reminderState, setReminderState] = useState<ReminderChatState>({ mode: "idle" });
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const prevConvIdRef = useRef<string | null>(conversationId);

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
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conv?.messages.length, busy, Object.keys(turnErrors).length, reminderState.mode]);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

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
  const showEmpty =
    messages.length === 0 &&
    !busy &&
    reminderState.mode === "idle" &&
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
            <div key={m.id} className="message-turn">
              <div className={`message message-${m.role}`}>
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

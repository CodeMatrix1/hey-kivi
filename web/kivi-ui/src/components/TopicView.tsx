import { useEffect, useState } from "react";
import { getConversation } from "../storage/conversations";
import {
  addManualNote,
  updateNote,
  updateTopicName,
} from "../storage/topics";
import type { Topic, TopicNote, TopicNoteType } from "../types";
import { formatDictationDate } from "../utils/historyDates";
import { groupNotesByType, TOPIC_NOTE_TYPE_OPTIONS } from "../utils/topicNotes";

interface TopicViewProps {
  topic: Topic;
  onBack: () => void;
  onOpenSource: (conversationId: string, messageId: string) => void;
  onOpenConversation: (conversationId: string) => void;
  onTopicsUpdated: () => void;
}

export function TopicView({
  topic,
  onBack,
  onOpenSource,
  onOpenConversation,
  onTopicsUpdated,
}: TopicViewProps) {
  const [nameDraft, setNameDraft] = useState(topic.name);
  const [showNewNote, setShowNewNote] = useState(false);
  const [newNoteText, setNewNoteText] = useState("");
  const [newNoteType, setNewNoteType] = useState<TopicNoteType>("context");
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<{ text: string; type: TopicNoteType } | null>(
    null,
  );

  useEffect(() => {
    setNameDraft(topic.name);
    setEditingNoteId(null);
    setEditDraft(null);
  }, [topic.id, topic.name]);

  const groups = groupNotesByType(topic.notes);

  function saveTopicName() {
    const trimmed = nameDraft.trim();
    if (!trimmed || trimmed === topic.name) return;
    try {
      updateTopicName(topic.id, trimmed);
      onTopicsUpdated();
    } catch {
      setNameDraft(topic.name);
    }
  }

  function startEditing(note: TopicNote) {
    setEditingNoteId(note.id);
    setEditDraft({ text: note.text, type: note.type });
    setShowNewNote(false);
  }

  function cancelEditing() {
    setEditingNoteId(null);
    setEditDraft(null);
  }

  function saveEditing(noteId: string) {
    if (!editDraft) return;
    const existing = topic.notes.find((n) => n.id === noteId);
    if (!existing) return;
    if (editDraft.text.trim() === existing.text && editDraft.type === existing.type) {
      cancelEditing();
      return;
    }
    try {
      updateNote(topic.id, noteId, {
        text: editDraft.text,
        type: editDraft.type,
      });
      cancelEditing();
      onTopicsUpdated();
    } catch {
      // keep editor open
    }
  }

  function handleAddManualNote() {
    const text = newNoteText.trim();
    if (!text) return;
    try {
      addManualNote(topic.id, { text, type: newNoteType });
      setNewNoteText("");
      setNewNoteType("context");
      setShowNewNote(false);
      onTopicsUpdated();
    } catch {
      // ignore empty text
    }
  }

  function cancelNewNote() {
    setShowNewNote(false);
    setNewNoteText("");
    setNewNoteType("context");
  }

  return (
    <div className="topic-view">
      <header className="topic-view-header">
        <button type="button" className="topic-back-btn" onClick={onBack}>
          ← Back
        </button>
        <input
          type="text"
          className="topic-name-input"
          value={nameDraft}
          onChange={(e) => setNameDraft(e.target.value)}
          onBlur={saveTopicName}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              (e.target as HTMLInputElement).blur();
            }
          }}
          aria-label="Topic name"
        />
        <p className="topic-view-subtitle">Your saved context</p>
      </header>

      {topic.notes.length === 0 && !showNewNote ? (
        <p className="topic-empty-hint">
          No notes yet. Add one below, or capture from a conversation using ⋮ on a message.
        </p>
      ) : (
        <div className="topic-note-sections">
          {groups.map((group) => (
            <section key={group.type} className="topic-note-section">
              <h3 className="topic-section-label">{group.label}</h3>
              <ul className="topic-note-list">
                {group.notes.map((note) => {
                  const isEditing = editingNoteId === note.id && editDraft;
                  const hasSource =
                    note.sourceConversationId && note.sourceMessageId;
                  return (
                    <li key={note.id} className="topic-note-row">
                      {isEditing ? (
                        <div className="topic-note-editor">
                          <div className="topic-note-editor-toolbar">
                            <select
                              value={editDraft.type}
                              onChange={(e) =>
                                setEditDraft({
                                  ...editDraft,
                                  type: e.target.value as TopicNoteType,
                                })
                              }
                              aria-label="Note type"
                            >
                              {TOPIC_NOTE_TYPE_OPTIONS.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                  {opt.label}
                                </option>
                              ))}
                            </select>
                            <div className="topic-note-editor-actions">
                              <button
                                type="button"
                                className="topic-note-action"
                                onClick={cancelEditing}
                              >
                                Cancel
                              </button>
                              <button
                                type="button"
                                className="topic-note-action topic-note-action-primary"
                                onClick={() => saveEditing(note.id)}
                                disabled={!editDraft.text.trim()}
                              >
                                Save
                              </button>
                            </div>
                          </div>
                          <textarea
                            className="topic-note-textarea"
                            rows={2}
                            value={editDraft.text}
                            onChange={(e) =>
                              setEditDraft({ ...editDraft, text: e.target.value })
                            }
                          />
                        </div>
                      ) : (
                        <>
                          <div className="topic-note-line">
                            <p className="topic-note-text">{note.text}</p>
                            <button
                              type="button"
                              className="topic-note-edit-btn"
                              onClick={() => startEditing(note)}
                              aria-label="Edit note"
                            >
                              Edit
                            </button>
                          </div>
                          {hasSource && (
                            <button
                              type="button"
                              className="topic-source-link"
                              onClick={() =>
                                onOpenSource(
                                  note.sourceConversationId!,
                                  note.sourceMessageId!,
                                )
                              }
                            >
                              From: {note.sourceConversationTitle || "Conversation"} ·{" "}
                              {formatDictationDate(note.createdAt)}
                            </button>
                          )}
                        </>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      )}

      {showNewNote ? (
        <div className="topic-new-note">
          <div className="topic-note-editor-toolbar">
            <select
              value={newNoteType}
              onChange={(e) => setNewNoteType(e.target.value as TopicNoteType)}
              aria-label="Note type"
            >
              {TOPIC_NOTE_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <div className="topic-note-editor-actions">
              <button type="button" className="topic-note-action" onClick={cancelNewNote}>
                Cancel
              </button>
              <button
                type="button"
                className="topic-note-action topic-note-action-primary"
                onClick={handleAddManualNote}
                disabled={!newNoteText.trim()}
              >
                Add
              </button>
            </div>
          </div>
          <textarea
            className="topic-note-textarea"
            rows={2}
            value={newNoteText}
            onChange={(e) => setNewNoteText(e.target.value)}
            placeholder="Decision, context, or open question…"
            autoFocus
          />
        </div>
      ) : (
        <button
          type="button"
          className="topic-new-note-btn"
          onClick={() => {
            setShowNewNote(true);
            cancelEditing();
          }}
        >
          + New note
        </button>
      )}

      {topic.conversationIds.length > 0 && (
        <section className="topic-conversations-section">
          <h3 className="topic-section-label">Conversations</h3>
          <ul className="topic-conversation-list">
            {topic.conversationIds.map((convId) => {
              const conv = getConversation(convId);
              return (
                <li key={convId}>
                  <button
                    type="button"
                    className="topic-conversation-link"
                    onClick={() => onOpenConversation(convId)}
                  >
                    {conv?.title || "Conversation"}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}

    </div>
  );
}

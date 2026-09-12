import { useCallback, useEffect, useState } from "react";
import {
  createReminder,
  deleteReminder,
  listReminders,
  updateReminder,
} from "../storage/reminders";
import type { Reminder } from "../types";
import { ReminderCard } from "./ReminderCard";
import {
  ReminderForm,
  dueAtToFormValues,
  formValuesToDueAt,
  type ReminderFormValues,
} from "./ReminderForm";

interface RemindersViewProps {
  tick: number;
  selectedId: string | null;
  showAdd: boolean;
  onSelectedIdChange: (id: string | null) => void;
  onShowAddChange: (show: boolean) => void;
  onReload: () => void;
  onViewConversation?: (conversationId: string) => void;
}

export function RemindersView({
  tick,
  selectedId,
  showAdd,
  onSelectedIdChange,
  onShowAddChange,
  onReload,
  onViewConversation,
}: RemindersViewProps) {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const now = new Date();

  const refresh = useCallback(() => {
    setReminders(listReminders());
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, tick]);

  useEffect(() => {
    if (selectedId && editingId !== selectedId) {
      setEditingId(null);
    }
  }, [selectedId, editingId]);

  function handleAdd(values: ReminderFormValues) {
    const created = createReminder({
      name: values.name.trim(),
      message: values.message.trim(),
      dueAt: formValuesToDueAt(values),
    });
    onShowAddChange(false);
    onSelectedIdChange(created.id);
    refresh();
    onReload();
  }

  function handleEdit(id: string, values: ReminderFormValues) {
    updateReminder(id, {
      name: values.name.trim(),
      message: values.message.trim(),
      dueAt: formValuesToDueAt(values),
    });
    setEditingId(null);
    refresh();
    onReload();
  }

  function handleDelete(id: string) {
    deleteReminder(id);
    if (selectedId === id) onSelectedIdChange(null);
    refresh();
    onReload();
  }

  const defaultDue = new Date(Date.now() + 60 * 60 * 1000);
  const selectedReminder = selectedId
    ? reminders.find((r) => r.id === selectedId) ?? null
    : null;

  return (
    <div className="reminders-view">
      <header className="reminders-header">
        <h2 className="page-title">Reminders</h2>
      </header>

      {showAdd && (
        <div className="reminder-form-panel">
          <ReminderForm
            initial={dueAtToFormValues(defaultDue.toISOString())}
            submitLabel="Add"
            onSubmit={handleAdd}
            onCancel={() => onShowAddChange(false)}
          />
        </div>
      )}

      {reminders.length === 0 && !showAdd ? (
        <p className="reminders-empty">
          No reminders yet. Ask Kivi in chat, or use + Add reminder when one appears in the
          panel.
        </p>
      ) : selectedReminder && !showAdd ? (
        <div className="reminder-detail-panel">
          {editingId === selectedReminder.id ? (
            <ReminderForm
              initial={dueAtToFormValues(
                selectedReminder.dueAt,
                selectedReminder.name,
                selectedReminder.message,
              )}
              submitLabel="Save"
              onSubmit={(values) => handleEdit(selectedReminder.id, values)}
              onCancel={() => setEditingId(null)}
            />
          ) : (
            <ReminderCard
              name={selectedReminder.name}
              message={selectedReminder.message}
              dueAt={selectedReminder.dueAt}
              now={now}
              className="reminder-card-detail"
              trailing={
                <div className="reminder-card-trailing">
                  <button
                    type="button"
                    className="reminder-action-btn"
                    onClick={() => setEditingId(selectedReminder.id)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="reminder-delete-btn"
                    aria-label="Delete reminder"
                    onClick={() => handleDelete(selectedReminder.id)}
                  >
                    ×
                  </button>
                </div>
              }
            />
          )}
          {selectedReminder.sourceConversationTitle && editingId !== selectedReminder.id && (
            <p className="reminder-row-source">
              Created from: {selectedReminder.sourceConversationTitle}
              {selectedReminder.sourceConversationId && onViewConversation && (
                <>
                  {" "}
                  <button
                    type="button"
                    className="link-btn"
                    onClick={() => onViewConversation(selectedReminder.sourceConversationId!)}
                  >
                    View conversation →
                  </button>
                </>
              )}
            </p>
          )}
        </div>
      ) : !showAdd ? (
        <p className="reminders-empty">Select a reminder from the sidebar.</p>
      ) : null}
    </div>
  );
}

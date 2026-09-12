import type { ReminderDraft } from "../types";
import { ReminderCard } from "./ReminderCard";

interface ReminderConfirmCardProps {
  draft: ReminderDraft;
  onAccept: () => void;
  onReject: () => void;
  onEdit: () => void;
  onContinueChat: () => void;
}

export function ReminderConfirmCard({
  draft,
  onAccept,
  onReject,
  onEdit,
  onContinueChat,
}: ReminderConfirmCardProps) {
  return (
    <ReminderCard
      className="reminder-card-confirm"
      name={draft.name}
      message={draft.message}
      dueAt={draft.dueAt}
      actions={
        <>
          <button type="button" className="reminder-action-btn" onClick={onEdit}>
            Edit
          </button>
          <button
            type="button"
            className="reminder-action-btn reminder-action-primary"
            onClick={onAccept}
          >
            Accept
          </button>
          <button type="button" className="reminder-action-btn" onClick={onReject}>
            Reject
          </button>
          <button type="button" className="reminder-action-btn" onClick={onContinueChat}>
            Continue chatting
          </button>
        </>
      }
    />
  );
}

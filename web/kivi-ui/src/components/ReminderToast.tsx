import type { Reminder } from "../types";
import { ReminderCard } from "./ReminderCard";

interface ReminderToastProps {
  reminder: Reminder;
  onDismiss: () => void;
}

export function ReminderToast({ reminder, onDismiss }: ReminderToastProps) {
  return (
    <div className="reminder-toast" role="status">
      <ReminderCard
        name={reminder.name}
        message={reminder.message}
        dueAt={reminder.dueAt}
        actions={
          <button type="button" className="reminder-action-btn reminder-toast-dismiss" onClick={onDismiss}>
            Dismiss
          </button>
        }
      />
    </div>
  );
}

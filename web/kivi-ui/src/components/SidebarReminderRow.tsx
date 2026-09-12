import type { Reminder } from "../types";
import { formatCompactDue, formatRelativeDue } from "../utils/reminderDisplay";

interface SidebarReminderRowProps {
  reminder: Reminder;
  now?: Date;
  isActive: boolean;
  isKeyboardFocus: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

export function SidebarReminderRow({
  reminder,
  now = new Date(),
  isActive,
  isKeyboardFocus,
  onSelect,
  onDelete,
}: SidebarReminderRowProps) {

  return (
    <div
      className={`sidebar-reminder-row ${isActive ? "active" : ""} ${isKeyboardFocus ? "keyboard-focus" : ""}`}
      role="option"
      aria-selected={isActive}
    >
      <button type="button" className="sidebar-item sidebar-reminder-item" onClick={onSelect}>
        <span className="sidebar-item-title">{reminder.name}</span>
        <span className="sidebar-reminder-meta">
          <span className="sidebar-reminder-exact">{formatCompactDue(reminder.dueAt, now)}</span>
          <span className="sidebar-reminder-relative">{formatRelativeDue(reminder.dueAt, now)}</span>
        </span>
      </button>
      <button
        type="button"
        className="reminder-delete-btn sidebar-reminder-delete"
        aria-label="Delete reminder"
        title="Delete reminder"
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onDelete();
        }}
      >
        ×
      </button>
    </div>
  );
}

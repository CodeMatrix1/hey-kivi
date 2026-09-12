import type { ReactNode } from "react";
import { formatExactDue, formatRelativeDue } from "../utils/reminderDisplay";

export interface ReminderCardProps {
  name: string;
  message: string;
  dueAt: string;
  now?: Date;
  showMessage?: boolean;
  actions?: ReactNode;
  trailing?: ReactNode;
  className?: string;
}

export function ReminderCard({
  name,
  message,
  dueAt,
  now = new Date(),
  showMessage = true,
  actions,
  trailing,
  className = "",
}: ReminderCardProps) {
  const exact = formatExactDue(dueAt, now);
  const relative = formatRelativeDue(dueAt, now);
  const messageDiffers =
    showMessage &&
    message.trim() &&
    message.trim().toLowerCase() !== name.trim().toLowerCase();

  return (
    <div className={`reminder-card ${className}`.trim()}>
      <div className="reminder-card-top">
        <div className="reminder-card-main">
          <span className="reminder-card-title">{name}</span>
          {messageDiffers && (
            <p className="reminder-card-message">{message}</p>
          )}
        </div>
        {trailing}
      </div>
      <div className="reminder-card-meta">
        <span className="reminder-card-exact">{exact}</span>
        <span className="reminder-card-relative">{relative}</span>
      </div>
      {actions && <div className="reminder-card-actions">{actions}</div>}
    </div>
  );
}

import { useState } from "react";

export interface ReminderFormValues {
  name: string;
  message: string;
  date: string;
  time: string;
}

interface ReminderFormProps {
  initial: ReminderFormValues;
  submitLabel: string;
  onSubmit: (values: ReminderFormValues) => void;
  onCancel: () => void;
}

export function ReminderForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: ReminderFormProps) {
  const [values, setValues] = useState(initial);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const due = new Date(`${values.date}T${values.time}`);
    if (Number.isNaN(due.getTime())) {
      setError("Please enter a valid date and time.");
      return;
    }
    if (due.getTime() <= Date.now()) {
      setError("Reminder time must be in the future.");
      return;
    }
    if (!values.name.trim() || !values.message.trim()) {
      setError("Name and message are required.");
      return;
    }
    setError(null);
    onSubmit(values);
  }

  return (
    <form className="reminder-form" onSubmit={handleSubmit}>
      <label>
        Name
        <input
          type="text"
          value={values.name}
          onChange={(e) => setValues((v) => ({ ...v, name: e.target.value }))}
        />
      </label>
      <label>
        Message
        <textarea
          rows={3}
          value={values.message}
          onChange={(e) => setValues((v) => ({ ...v, message: e.target.value }))}
        />
      </label>
      <div className="reminder-form-row">
        <label>
          Date
          <input
            type="date"
            value={values.date}
            onChange={(e) => setValues((v) => ({ ...v, date: e.target.value }))}
          />
        </label>
        <label>
          Time
          <input
            type="time"
            value={values.time}
            onChange={(e) => setValues((v) => ({ ...v, time: e.target.value }))}
          />
        </label>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="reminder-form-actions">
        <button type="button" className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn-primary">{submitLabel}</button>
      </div>
    </form>
  );
}

export function dueAtToFormValues(dueAt: string, name = "", message = ""): ReminderFormValues {
  const d = new Date(dueAt);
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    name,
    message,
    date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
  };
}

export function formValuesToDueAt(values: ReminderFormValues): string {
  return new Date(`${values.date}T${values.time}`).toISOString();
}

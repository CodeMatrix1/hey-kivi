const MS_MINUTE = 60 * 1000;
const MS_HOUR = 60 * MS_MINUTE;
const MS_DAY = 24 * MS_HOUR;

function isSameCalendarDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function isTomorrow(due: Date, now: Date): boolean {
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  return isSameCalendarDay(due, tomorrow);
}

/** Compact due line for sidebar, e.g. "Today · 8:44 PM". */
export function formatCompactDue(dueAt: string, now: Date = new Date()): string {
  const due = new Date(dueAt);
  const timePart = due.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
  let dayLabel: string;
  if (isSameCalendarDay(due, now)) {
    dayLabel = "Today";
  } else if (isTomorrow(due, now)) {
    dayLabel = "Tomorrow";
  } else {
    dayLabel = due.toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  }
  return `${dayLabel} · ${timePart}`;
}

/** Full exact due time, e.g. "9:00 PM today" or "9:00 PM on Friday, Sep 12". */
export function formatExactDue(dueAt: string, now: Date = new Date()): string {
  const due = new Date(dueAt);
  const timePart = due.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
  if (isSameCalendarDay(due, now)) {
    return `${timePart} today`;
  }
  if (isTomorrow(due, now)) {
    return `${timePart} tomorrow`;
  }
  const weekday = due.toLocaleDateString(undefined, { weekday: "long" });
  const monthDay = due.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return `${timePart} on ${weekday}, ${monthDay}`;
}

/** @deprecated Use formatExactDue */
export function formatAbsoluteDue(dueAt: string, now: Date = new Date()): string {
  return formatExactDue(dueAt, now);
}

/** Largest useful unit; never seconds. */
export function formatRelativeDue(dueAt: string, now: Date = new Date()): string {
  const diff = new Date(dueAt).getTime() - now.getTime();
  if (diff <= 0 || diff < MS_MINUTE) return "due";
  if (diff > 3 * MS_DAY) {
    const days = Math.floor(diff / MS_DAY);
    return `in ${days} days`;
  }
  if (diff > 5 * MS_HOUR) {
    const hours = Math.floor(diff / MS_HOUR);
    return `in ${hours} hours`;
  }
  if (diff >= MS_MINUTE) {
    const minutes = Math.floor(diff / MS_MINUTE);
    return `in ${minutes} minutes`;
  }
  return "due";
}

export function containsSecondsUnit(text: string): boolean {
  return /\b\d+\s*(?:seconds?|secs?|s)\b/i.test(text) || /\d{1,2}:\d{2}/.test(text);
}

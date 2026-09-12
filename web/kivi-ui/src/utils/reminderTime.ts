const MONTHS: Record<string, number> = {
  january: 0,
  jan: 0,
  february: 1,
  feb: 1,
  march: 2,
  mar: 2,
  april: 3,
  apr: 3,
  may: 4,
  june: 5,
  jun: 5,
  july: 6,
  jul: 6,
  august: 7,
  aug: 7,
  september: 8,
  sep: 8,
  sept: 8,
  october: 9,
  oct: 9,
  november: 10,
  nov: 10,
  december: 11,
  dec: 11,
};

const WEEKDAYS: Record<string, number> = {
  sunday: 0,
  sun: 0,
  monday: 1,
  mon: 1,
  tuesday: 2,
  tue: 2,
  tues: 2,
  wednesday: 3,
  wed: 3,
  thursday: 4,
  thu: 4,
  thur: 4,
  thurs: 4,
  friday: 5,
  fri: 5,
  saturday: 6,
  sat: 6,
};

export interface TemporalMatch {
  text: string;
  index: number;
  length: number;
}

const TEMPORAL_PATTERNS: RegExp[] = [
  /\bin\s+\d+\s+(?:minute|minutes|min|mins|hour|hours|hr|hrs|day|days)\b/gi,
  /\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\s+(?:today|tomorrow|tonight)\b/gi,
  /\b(?:today|tomorrow|tonight)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)\b/gi,
  /\b(?:today|tomorrow|tonight)\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)\b/gi,
  /\b(?:today|tomorrow|tonight)\s+at\s+\d{1,2}(?::\d{2})?\b/gi,
  /\bon\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?/gi,
  /\bon\s+\d{1,2}\/\d{1,2}(?:\/\d{2,4})?(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?/gi,
  /\b(?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?/gi,
  /\b(?:today|tomorrow|tonight)\b/gi,
  /\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)\b/gi,
  /\bat\s+\d{1,2}(?::\d{2})?\b/gi,
  /\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b/gi,
];

function parseClock(hour: number, minute: number, meridiem?: string): { hour: number; minute: number } {
  let h = hour;
  const m = minute;
  if (meridiem) {
    const lower = meridiem.toLowerCase();
    if (lower === "pm" && h < 12) h += 12;
    if (lower === "am" && h === 12) h = 0;
  }
  return { hour: h, minute: m };
}

function setLocalTime(base: Date, hour: number, minute: number): Date {
  const d = new Date(base);
  d.setHours(hour, minute, 0, 0);
  return d;
}

function addDays(base: Date, days: number): Date {
  const d = new Date(base);
  d.setDate(d.getDate() + days);
  return d;
}

function nextWeekday(from: Date, targetDay: number): Date {
  const d = new Date(from);
  d.setHours(0, 0, 0, 0);
  const current = d.getDay();
  let delta = (targetDay - current + 7) % 7;
  if (delta === 0) delta = 7;
  return addDays(d, delta);
}

function parseMonthDay(text: string, now: Date): Date | null {
  const m = text.match(
    /(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?/i,
  );
  if (!m) return null;
  const month = MONTHS[m[1].toLowerCase()];
  const day = parseInt(m[2], 10);
  let year = now.getFullYear();
  const candidate = new Date(year, month, day, 0, 0, 0, 0);
  if (candidate < new Date(now.getFullYear(), now.getMonth(), now.getDate())) {
    year += 1;
  }
  return new Date(year, month, day, 0, 0, 0, 0);
}

function extractClock(text: string): { hour: number; minute: number } | null {
  const atMatch = text.match(/\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/i);
  if (atMatch) {
    const hour = parseInt(atMatch[1], 10);
    const minute = atMatch[2] ? parseInt(atMatch[2], 10) : 0;
    return parseClock(hour, minute, atMatch[3]);
  }
  const m = text.match(/(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/i);
  if (!m) return null;
  const hour = parseInt(m[1], 10);
  const minute = m[2] ? parseInt(m[2], 10) : 0;
  const meridiem = m[3];
  if (!meridiem && (hour > 23 || minute > 59)) return null;
  return parseClock(hour, minute, meridiem);
}

function isBetterTemporalMatch(candidate: TemporalMatch, current: TemporalMatch): boolean {
  if (candidate.index < current.index) return true;
  if (candidate.index > current.index) return false;
  return candidate.length > current.length;
}

/** Find the first recognizable temporal expression in text. */
export function findTemporalExpression(text: string): TemporalMatch | null {
  let best: TemporalMatch | null = null;
  for (const pattern of TEMPORAL_PATTERNS) {
    pattern.lastIndex = 0;
    const match = pattern.exec(text);
    if (!match) continue;
    const candidate = { text: match[0], index: match.index, length: match[0].length };
    if (!best || isBetterTemporalMatch(candidate, best)) {
      best = candidate;
    }
  }
  return best;
}

/** Whether text contains a recognizable date/time expression. */
export function hasRecognizableDateTime(text: string): boolean {
  return findTemporalExpression(text) !== null;
}

function inferDayBaseFromText(text: string, now: Date, fallback: Date): Date {
  const lower = text.toLowerCase();
  if (/\btomorrow\b/.test(lower)) {
    const dayBase = new Date(now);
    dayBase.setHours(0, 0, 0, 0);
    return addDays(dayBase, 1);
  }
  if (/\btonight\b/.test(lower)) {
    return new Date(now);
  }
  if (/\btoday\b/.test(lower)) {
    const dayBase = new Date(now);
    dayBase.setHours(0, 0, 0, 0);
    return dayBase;
  }
  return fallback;
}

/** Resolve temporal expression to absolute ISO dueAt in local timezone. */
export function resolveDueAt(text: string, now: Date = new Date()): string | null {
  const temporal = findTemporalExpression(text);
  if (!temporal) return null;
  const expr = temporal.text.toLowerCase();

  const relative = expr.match(/\bin\s+(\d+)\s+(minute|minutes|min|mins|hour|hours|hr|hrs|day|days)\b/i);
  if (relative) {
    const amount = parseInt(relative[1], 10);
    const unit = relative[2].toLowerCase();
    const d = new Date(now);
    if (unit.startsWith("min")) d.setMinutes(d.getMinutes() + amount);
    else if (unit.startsWith("hour") || unit.startsWith("hr")) d.setHours(d.getHours() + amount);
    else d.setDate(d.getDate() + amount);
    return d.toISOString();
  }

  let dayBase = new Date(now);
  dayBase.setHours(0, 0, 0, 0);

  if (/\btonight\b/.test(expr)) {
    dayBase = new Date(now);
  } else if (/\btomorrow\b/.test(expr)) {
    dayBase = addDays(dayBase, 1);
  } else if (/\btoday\b/.test(expr)) {
    dayBase = new Date(now);
    dayBase.setHours(0, 0, 0, 0);
  } else {
    const weekdayKey = Object.keys(WEEKDAYS).find((k) => new RegExp(`\\b${k}\\b`, "i").test(expr));
    if (weekdayKey) {
      dayBase = nextWeekday(now, WEEKDAYS[weekdayKey]);
    } else if (/\bon\s+/.test(expr)) {
      const slash = expr.match(/(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?/);
      if (slash) {
        const month = parseInt(slash[1], 10) - 1;
        const day = parseInt(slash[2], 10);
        let year = slash[3] ? parseInt(slash[3], 10) : now.getFullYear();
        if (year < 100) year += 2000;
        dayBase = new Date(year, month, day, 0, 0, 0, 0);
      } else {
        const parsed = parseMonthDay(expr, now);
        if (!parsed) return null;
        dayBase = parsed;
      }
    }
  }

  const clock = extractClock(expr) ?? extractClock(text);
  if (clock) {
    const dayForClock = inferDayBaseFromText(text, now, dayBase);
    const due = setLocalTime(dayForClock, clock.hour, clock.minute);
    return due.toISOString();
  }

  if (/\btonight\b/.test(expr)) {
    const due = setLocalTime(dayBase, 20, 0);
    return due.toISOString();
  }

  if (/\b(?:today|tomorrow)\b/.test(expr) && !/\bat\b/.test(expr)) {
    const due = setLocalTime(dayBase, 9, 0);
    return due.toISOString();
  }

  return null;
}

export function isDueAtInFuture(dueAt: string, now: Date = new Date()): boolean {
  return new Date(dueAt).getTime() > now.getTime();
}

export function getTemporalSpan(text: string): { start: number; end: number; text: string } | null {
  const m = findTemporalExpression(text);
  if (!m) return null;
  return { start: m.index, end: m.index + m.length, text: m.text };
}

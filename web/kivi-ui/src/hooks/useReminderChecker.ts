import { useCallback, useEffect, useRef, useState } from "react";
import { REMINDER_ACTIVE_INTERVAL_MS, REMINDER_TOAST_DURATION_MS } from "../utils/reminderConstants";
import { checkReminders } from "../utils/reminderChecker";
import { listReminders } from "../storage/reminders";
import type { Reminder } from "../types";

export interface ReminderCheckerState {
  activeToast: Reminder | null;
  tick: number;
  reload: () => void;
  dismissToast: () => void;
}

export function useReminderChecker(): ReminderCheckerState {
  const [activeToast, setActiveToast] = useState<Reminder | null>(null);
  const [tick, setTick] = useState(0);
  const firedIdsRef = useRef<Set<string>>(new Set());
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const showingToastRef = useRef(false);

  const clearToastTimer = useCallback(() => {
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
      toastTimerRef.current = null;
    }
  }, []);

  const showToast = useCallback(
    (reminder: Reminder) => {
      if (showingToastRef.current) return;
      firedIdsRef.current.add(reminder.id);
      showingToastRef.current = true;
      setActiveToast(reminder);
      clearToastTimer();
      toastTimerRef.current = setTimeout(() => {
        showingToastRef.current = false;
        setActiveToast(null);
        toastTimerRef.current = null;
      }, REMINDER_TOAST_DURATION_MS);
    },
    [clearToastTimer],
  );

  const performCheck = useCallback(() => {
    const now = new Date();
    const reminders = listReminders();
    const result = checkReminders(now, reminders, firedIdsRef.current);
    setTick((t) => t + 1);

    if (result.toasts.length > 0) {
      showToast(result.toasts[0]);
    }

    if (result.needsActiveRefresh) {
      if (!intervalRef.current) {
        intervalRef.current = setInterval(() => {
          const innerNow = new Date();
          const innerReminders = listReminders();
          const inner = checkReminders(innerNow, innerReminders, firedIdsRef.current);
          setTick((t) => t + 1);
          if (inner.toasts.length > 0) {
            showToast(inner.toasts[0]);
          }
          if (!inner.needsActiveRefresh && intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }, REMINDER_ACTIVE_INTERVAL_MS);
      }
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, [showToast]);

  const reload = useCallback(() => {
    performCheck();
  }, [performCheck]);

  const dismissToast = useCallback(() => {
    clearToastTimer();
    showingToastRef.current = false;
    setActiveToast(null);
  }, [clearToastTimer]);

  useEffect(() => {
    performCheck();
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      clearToastTimer();
    };
  }, []);

  return { activeToast, tick, reload, dismissToast };
}

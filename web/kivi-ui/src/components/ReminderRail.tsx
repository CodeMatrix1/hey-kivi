import { useCallback, useEffect, useMemo, useState } from "react";
import { useArrowListNav } from "../hooks/useArrowListNav";
import type { Reminder } from "../types";
import { SidebarCollapsibleSection } from "./SidebarCollapsibleSection";
import { SidebarReminderRow } from "./SidebarReminderRow";

const REM_EXPANDED_KEY = "kivi_reminder_rail_expanded";

function loadExpanded(): boolean {
  try {
    const raw = localStorage.getItem(REM_EXPANDED_KEY);
    return raw === null ? true : raw === "true";
  } catch {
    return true;
  }
}

function countUpcoming(reminders: Reminder[], now: Date): number {
  return reminders.filter((r) => new Date(r.dueAt).getTime() > now.getTime()).length;
}

function upcomingSubtitle(reminders: Reminder[], now: Date): string | undefined {
  if (reminders.length === 0) return undefined;
  const upcoming = countUpcoming(reminders, now);
  if (upcoming === 1) return "1 upcoming";
  if (upcoming > 1) return `${upcoming} upcoming`;
  if (reminders.length === 1) return "1 reminder";
  return `${reminders.length} reminders`;
}

interface ReminderRailProps {
  reminders: Reminder[];
  tick: number;
  activeReminderId: string | null;
  remindersViewActive: boolean;
  onSelectReminder: (id: string) => void;
  onDeleteReminder: (id: string) => void;
  onNewReminder: () => void;
}

export function ReminderRail({
  reminders,
  tick,
  activeReminderId,
  remindersViewActive,
  onSelectReminder,
  onDeleteReminder,
  onNewReminder,
}: ReminderRailProps) {
  const [expanded, setExpanded] = useState(loadExpanded);
  const now = useMemo(() => new Date(), [tick]);
  const subtitle = upcomingSubtitle(reminders, now);

  const navEnabled = expanded && reminders.length > 0;

  const { focusIndex: remFocusIndex, setItemRef: setRemItemRef } = useArrowListNav({
    items: reminders,
    enabled: navEnabled,
    selectedId: activeReminderId,
    getId: useCallback((r: Reminder) => r.id, []),
    onSelect: onSelectReminder,
  });

  useEffect(() => {
    localStorage.setItem(REM_EXPANDED_KEY, String(expanded));
  }, [expanded]);

  return (
    <aside className={`reminder-rail ${expanded ? "expanded" : "collapsed"}`}>
      <SidebarCollapsibleSection
        title="reminders"
        subtitle={subtitle}
        expanded={expanded}
        onToggle={() => setExpanded((v) => !v)}
        addLabel="+ Add reminder"
        addClassName="btn-new-reminder"
        onAdd={onNewReminder}
      >
        {reminders.length === 0 ? (
          <p className="sidebar-empty sidebar-reminder-empty">No upcoming reminders</p>
        ) : (
          <div className="sidebar-reminder-list" role="listbox" aria-label="Reminders">
            {reminders.map((r, index) => (
              <div key={r.id} ref={setRemItemRef(index)}>
                <SidebarReminderRow
                  reminder={r}
                  now={now}
                  isActive={activeReminderId === r.id && remindersViewActive}
                  isKeyboardFocus={remFocusIndex === index}
                  onSelect={() => onSelectReminder(r.id)}
                  onDelete={() => onDeleteReminder(r.id)}
                />
              </div>
            ))}
          </div>
        )}
      </SidebarCollapsibleSection>
    </aside>
  );
}

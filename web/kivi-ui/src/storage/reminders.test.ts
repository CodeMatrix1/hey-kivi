import { beforeEach, describe, expect, it } from "vitest";
import {
  clearAllReminders,
  createReminder,
  deleteReminder,
  listReminders,
  updateReminder,
} from "./reminders";

beforeEach(() => {
  clearAllReminders();
});

describe("reminders storage", () => {
  it("creates and lists reminders sorted by dueAt", () => {
    const later = createReminder({
      name: "Later",
      message: "Later msg",
      dueAt: new Date("2026-09-15T10:00:00").toISOString(),
    });
    const sooner = createReminder({
      name: "Sooner",
      message: "Soon msg",
      dueAt: new Date("2026-09-13T10:00:00").toISOString(),
    });
    const list = listReminders();
    expect(list[0].id).toBe(sooner.id);
    expect(list[1].id).toBe(later.id);
  });

  it("updates reminder", () => {
    const r = createReminder({
      name: "A",
      message: "B",
      dueAt: new Date("2026-09-15T10:00:00").toISOString(),
    });
    updateReminder(r.id, { name: "Updated" });
    expect(listReminders()[0].name).toBe("Updated");
  });

  it("deletes reminder", () => {
    const r = createReminder({
      name: "A",
      message: "B",
      dueAt: new Date("2026-09-15T10:00:00").toISOString(),
    });
    expect(deleteReminder(r.id)).toBe(true);
    expect(listReminders()).toHaveLength(0);
  });

  it("does not persist status fields", () => {
    createReminder({
      name: "A",
      message: "B",
      dueAt: new Date("2026-09-15T10:00:00").toISOString(),
    });
    const raw = localStorage.getItem("kivi_reminders_v1");
    expect(raw).not.toContain("pending");
    expect(raw).not.toContain("dismissed");
    expect(raw).not.toContain("completed");
    expect(raw).not.toContain("fired");
  });
});

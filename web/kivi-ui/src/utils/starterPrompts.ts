import type { QueryCase } from "../types";

const STARTER_IDS = [
  "recall-maya-arjun",
  "prep-payments-review",
  "recall-travel-summary",
  "find-polish-train",
  "plan-travel-itinerary",
  "lexical-name-spell",
] as const;

export function pickStarterPrompts(cases: QueryCase[]): QueryCase[] {
  const byId = new Map(cases.map((c) => [c.id, c]));
  return STARTER_IDS.map((id) => byId.get(id)).filter(Boolean) as QueryCase[];
}

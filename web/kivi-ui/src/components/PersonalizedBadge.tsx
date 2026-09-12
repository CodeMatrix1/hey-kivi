import type { DecisionTrace } from "../types";

export function showPersonalizedBadge(trace?: DecisionTrace): boolean {
  if (!trace || trace.decision === "abstain") return false;

  if ((trace.applied_preferences?.length ?? 0) > 0) return true;

  const tools = trace.tools_used ?? [];
  if (
    tools.includes("hindsight_recall") &&
    (trace.memories_considered?.length ?? 0) > 0
  ) {
    return true;
  }

  return false;
}

export function PersonalizedBadge({ trace }: { trace?: DecisionTrace }) {
  if (!showPersonalizedBadge(trace)) return null;
  return <span className="personalized-badge">✨ Personalized</span>;
}

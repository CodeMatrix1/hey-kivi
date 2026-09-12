import type { DecisionTrace, Dictation } from "../types";

export interface HistorySource {
  quote: string;
  dictationId?: string;
  createdAt?: string;
  viewable: boolean;
}

/** Dictation find/polish only — not cross-recall. */
export function showFromHistory(trace?: DecisionTrace): boolean {
  if (!trace || trace.decision === "abstain") return false;
  if (trace.selected_dictation_id) return true;
  return (trace.selected_dictation_ids?.length ?? 0) > 0;
}

function candidatePreview(
  trace: DecisionTrace,
  dictationId: string,
): { quote?: string; createdAt?: string } {
  const candidate = trace.candidates?.find((c) => c.id === dictationId);
  if (!candidate) return {};
  return {
    quote: candidate.formatted_preview,
    createdAt: candidate.created_at,
  };
}

export function extractHistorySources(
  trace: DecisionTrace,
  dictationById: Map<string, Dictation>,
): HistorySource[] {
  const ids =
    trace.selected_dictation_ids?.length
      ? trace.selected_dictation_ids
      : trace.selected_dictation_id
        ? [trace.selected_dictation_id]
        : [];

  return ids.map((id) => {
    const dictation = dictationById.get(id);
    const fallback = candidatePreview(trace, id);
    return {
      dictationId: id,
      quote:
        dictation?.formatted ||
        dictation?.asr ||
        fallback.quote ||
        "Historical note",
      createdAt: dictation?.created_at || fallback.createdAt,
      viewable: Boolean(dictation),
    };
  });
}

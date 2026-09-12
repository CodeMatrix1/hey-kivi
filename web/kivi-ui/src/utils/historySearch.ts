import type { Dictation } from "../types";

export function searchDictations(dictations: Dictation[], query: string): Dictation[] {
  const q = query.trim().toLowerCase();
  if (!q) return dictations;
  return dictations.filter((d) => {
    const formatted = (d.formatted || "").toLowerCase();
    const asr = (d.asr || "").toLowerCase();
    return formatted.includes(q) || asr.includes(q);
  });
}

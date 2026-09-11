/** Load query library (copy of evals/cases/query_cases.json — run evals.sync_cases after edits). */

let _cache = null;

export async function loadQueryLibrary() {
  if (_cache) return _cache;
  const res = await fetch("/static/assets/query_cases.json", { cache: "no-store" });
  if (!res.ok) throw new Error(`query_cases.json: ${res.status}`);
  const cases = await res.json();
  _cache = cases.map((item) => ({
    id: item.id,
    category: item.category,
    title: item.title,
    prompt: item.message,
    expected: item.expected_summary || "",
  }));
  return _cache;
}

/** @deprecated use loadQueryLibrary() */
export const queryLibrary = [];

import type { LexicalMapping } from "../types";

export interface PreferenceGroup {
  preferred: string;
  inputs: string[];
}

function norm(s: string): string {
  return s.trim().toLowerCase();
}

export function groupLexicalMappings(mappings: LexicalMapping[]): PreferenceGroup[] {
  const groups = new Map<string, PreferenceGroup>();

  for (const m of mappings) {
    const key = norm(m.canonical);
    const existing = groups.get(key);
    if (existing) {
      if (!existing.inputs.some((i) => norm(i) === norm(m.alias))) {
        existing.inputs.push(m.alias);
      }
    } else {
      groups.set(key, { preferred: m.canonical, inputs: [m.alias] });
    }
  }

  return Array.from(groups.values()).sort((a, b) =>
    a.preferred.localeCompare(b.preferred),
  );
}

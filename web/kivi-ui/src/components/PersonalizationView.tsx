import { useCallback, useEffect, useState } from "react";
import { getLexical, saveLexicalPreference } from "../api/client";
import { getLearningFeed } from "../storage/conversations";
import type { LearningEvent, LexicalMapping } from "../types";
import { groupLexicalMappings, type PreferenceGroup } from "../utils/lexicalGroups";
import { PreferenceCard } from "./PreferenceCard";
import { PreferenceForm } from "./PreferenceForm";

interface PersonalizationViewProps {
  userId: string;
}

export function PersonalizationView({ userId }: PersonalizationViewProps) {
  const [mappings, setMappings] = useState<LexicalMapping[]>([]);
  const [learning, setLearning] = useState<LearningEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [formMode, setFormMode] = useState<"none" | "add" | "edit">("none");
  const [editingGroup, setEditingGroup] = useState<PreferenceGroup | null>(null);

  const loadPreferences = useCallback(async () => {
    const lex = await getLexical(userId);
    setMappings(lex.mappings || []);
  }, [userId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        await loadPreferences();
        if (!cancelled) setLearning(getLearningFeed());
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load personalization");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, loadPreferences]);

  const groups = groupLexicalMappings(mappings);

  async function handleSave(
    preferred: string,
    inputs: string[],
    previousPreferred?: string,
  ) {
    const snapshot = mappings;
    try {
      const result = await saveLexicalPreference(userId, {
        preferred,
        inputs,
        previous_preferred: previousPreferred,
      });
      setMappings(result.mappings || []);
      setFormMode("none");
      setEditingGroup(null);
      setError(null);
    } catch (err) {
      setMappings(snapshot);
      throw err;
    }
  }

  return (
    <div className="personalization-view">
      <header className="page-header">
        <h2 className="page-title">personalization</h2>
        <p className="muted">How Kivi adapts to you</p>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <section className="card">
        <h3>Preferences</h3>
        <p className="section-desc muted">How you like Kivi to respond</p>

        {loading ? (
          <p className="muted">Loading preferences…</p>
        ) : formMode === "add" ? (
          <PreferenceForm
            onCancel={() => setFormMode("none")}
            onSave={handleSave}
          />
        ) : formMode === "edit" && editingGroup ? (
          <PreferenceForm
            initial={editingGroup}
            onCancel={() => {
              setFormMode("none");
              setEditingGroup(null);
            }}
            onSave={handleSave}
          />
        ) : (
          <>
            {groups.length === 0 ? (
              <p className="muted">No preferences yet.</p>
            ) : (
              groups.map((g) => (
                <PreferenceCard
                  key={g.preferred}
                  group={g}
                  onEdit={() => {
                    setEditingGroup(g);
                    setFormMode("edit");
                  }}
                />
              ))
            )}
            <button
              type="button"
              className="btn-secondary add-pref-btn"
              onClick={() => setFormMode("add")}
            >
              + Add preference
            </button>
          </>
        )}
      </section>

      <section className="card">
        <h3>Recent learning</h3>
        <p className="section-desc muted">What Kivi has noticed recently</p>
        {learning.length === 0 ? (
          <p className="muted">No learning events this session.</p>
        ) : (
          <ul className="learning-list">
            {learning.map((e) => (
              <li key={e.id}>
                <span className={`learn-icon ${e.kind}`}>
                  {e.kind === "learned" ? "✓" : "·"}
                </span>
                <span>{e.summary}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="about-memory card">
        <h3>About Kivi&apos;s memory</h3>
        <p>Kivi learns from your conversations automatically.</p>
        <p>If something is wrong, tell Kivi and it can update its understanding.</p>
      </section>
    </div>
  );
}

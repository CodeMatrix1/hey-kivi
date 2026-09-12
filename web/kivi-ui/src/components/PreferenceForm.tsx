import { useEffect, useState } from "react";
import type { PreferenceGroup } from "../utils/lexicalGroups";

interface PreferenceFormProps {
  initial?: PreferenceGroup | null;
  onCancel: () => void;
  onSave: (preferred: string, inputs: string[], previousPreferred?: string) => Promise<void>;
}

export function PreferenceForm({ initial, onCancel, onSave }: PreferenceFormProps) {
  const [preferred, setPreferred] = useState(initial?.preferred || "");
  const [inputs, setInputs] = useState<string[]>(initial?.inputs.length ? initial.inputs : [""]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPreferred(initial?.preferred || "");
    setInputs(initial?.inputs.length ? initial.inputs : [""]);
    setError(null);
  }, [initial]);

  function validate(): string | null {
    const p = preferred.trim();
    if (!p) return "Preferred term is required.";
    const cleaned = inputs.map((i) => i.trim()).filter(Boolean);
    if (cleaned.length === 0) return "Add at least one input phrase.";
    const seen = new Set<string>();
    for (const inp of cleaned) {
      const key = inp.toLowerCase();
      if (seen.has(key)) return `Duplicate phrase: "${inp}"`;
      seen.add(key);
    }
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setBusy(true);
    setError(null);
    const cleaned = inputs.map((i) => i.trim()).filter(Boolean);
    const previousPreferred = initial?.preferred;
    try {
      await onSave(preferred.trim(), cleaned, previousPreferred);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save preference");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="preference-form card" onSubmit={handleSubmit}>
      <h3>{initial ? "Edit preference" : "Add preference"}</h3>

      <label className="field">
        Preferred term
        <input
          type="text"
          value={preferred}
          onChange={(e) => setPreferred(e.target.value)}
          disabled={busy}
          placeholder="petrol bunk"
        />
      </label>

      <div className="field">
        <span>Input phrases</span>
        <p className="field-hint muted">
          Add every phrase Kivi should replace — one row per phrase. You can add as many
          as you need.
        </p>
        {inputs.map((inp, idx) => (
          <div key={idx} className="phrase-row">
            <span className="phrase-index" aria-hidden="true">{idx + 1}</span>
            <input
              type="text"
              value={inp}
              onChange={(e) => {
                const next = [...inputs];
                next[idx] = e.target.value;
                setInputs(next);
              }}
              disabled={busy}
              placeholder={idx === 0 ? "gas station" : "another phrase…"}
            />
            {inputs.length > 1 && (
              <button
                type="button"
                className="btn-icon"
                onClick={() => setInputs(inputs.filter((_, i) => i !== idx))}
                disabled={busy}
                aria-label="Remove phrase"
              >
                ×
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          className="btn-text"
          onClick={() => setInputs([...inputs, ""])}
          disabled={busy}
        >
          + Add another phrase
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="form-actions">
        <button type="button" className="btn-secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}

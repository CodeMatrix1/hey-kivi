import { useMemo, useState } from "react";
import type { Dictation } from "../types";
import { deriveTitle } from "../storage/conversations";
import { dateGroupLabel, formatDictationTime } from "../utils/historyDates";
import { searchDictations } from "../utils/historySearch";

interface HistoryViewProps {
  dictations: Dictation[];
  totalCount: number;
  returnedCount: number;
  loading: boolean;
  onSelect: (id: string) => void;
  onAddNote?: (text: string) => Promise<void>;
}

export function HistoryView({
  dictations,
  totalCount,
  returnedCount,
  loading,
  onSelect,
  onAddNote,
}: HistoryViewProps) {
  const [query, setQuery] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const trimmedQuery = query.trim();

  const filtered = useMemo(
    () => searchDictations(dictations, query),
    [dictations, query],
  );

  const sorted = [...filtered].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  let lastGroup = "";

  return (
    <div className="history-view">
      <header className="page-header history-header">
        <div>
          <h2 className="page-title">history</h2>
          <p className="muted history-count">{totalCount} takes</p>
        </div>
        {onAddNote && (
          <button
            type="button"
            className="history-add-toggle"
            onClick={() => {
              setShowAdd((open) => !open);
              setAddError(null);
            }}
            aria-expanded={showAdd}
            aria-controls="history-add-panel"
          >
            {showAdd ? "×" : "+ add"}
          </button>
        )}
      </header>

      {onAddNote && showAdd && (
        <form
          id="history-add-panel"
          className="history-add-note"
          onSubmit={async (e) => {
            e.preventDefault();
            const text = noteText.trim();
            if (!text || adding) return;
            setAdding(true);
            setAddError(null);
            try {
              await onAddNote(text);
              setNoteText("");
              setShowAdd(false);
            } catch {
              setAddError("Could not add note.");
            } finally {
              setAdding(false);
            }
          }}
        >
          <label className="sr-only" htmlFor="history-add-note">Add a text note</label>
          <textarea
            id="history-add-note"
            className="history-add-note-input"
            placeholder="Text note…"
            rows={2}
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            disabled={loading || adding}
            autoFocus
          />
          <div className="history-add-note-actions">
            <button
              type="submit"
              className="history-add-note-submit"
              disabled={loading || adding || !noteText.trim()}
            >
              {adding ? "…" : "Add"}
            </button>
            <button
              type="button"
              className="history-add-note-cancel"
              onClick={() => {
                setShowAdd(false);
                setNoteText("");
                setAddError(null);
              }}
              disabled={adding}
            >
              Cancel
            </button>
          </div>
          {addError && <p className="history-add-note-error" role="alert">{addError}</p>}
        </form>
      )}

      <label className="history-search-field">
        <span className="sr-only">Search your history</span>
        <input
          type="search"
          className="history-search-input"
          placeholder="Search your history…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={loading}
        />
      </label>

      {loading ? (
        <p className="muted">Loading takes…</p>
      ) : dictations.length === 0 ? (
        <p className="muted">No takes yet.</p>
      ) : trimmedQuery && sorted.length === 0 ? (
        <p className="muted history-empty">No matching takes in the loaded history.</p>
      ) : (
        <div className="history-list-scroll">
          <ul className="history-list">
            {sorted.map((d) => {
              const group = dateGroupLabel(d.created_at);
              const showHeader = group !== lastGroup;
              lastGroup = group;
              const text = d.formatted || d.asr;
              return (
                <li key={d.id}>
                  {showHeader && <div className="history-date-label">{group}</div>}
                  <button
                    type="button"
                    className="history-item"
                    onClick={() => onSelect(d.id)}
                  >
                    <span className="history-snippet">{deriveTitle(text, 80)}</span>
                    <span className="history-time">{formatDictationTime(d.created_at)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {trimmedQuery && returnedCount < totalCount && (
        <p className="muted history-footer">
          Searching within {returnedCount} loaded takes (of {totalCount} total).
        </p>
      )}

      {!trimmedQuery && returnedCount < totalCount && (
        <p className="muted history-footer">
          Showing {returnedCount} of {totalCount} takes
        </p>
      )}
    </div>
  );
}

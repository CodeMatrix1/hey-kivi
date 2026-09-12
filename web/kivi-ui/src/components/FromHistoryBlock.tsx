import type { DecisionTrace, Dictation } from "../types";
import { extractHistorySources, showFromHistory } from "../utils/historyProvenance";
import { formatDictationDate, formatDictationTime } from "../utils/historyDates";
import { HistoryIcon } from "./HistoryIcon";

interface FromHistoryBlockProps {
  trace?: DecisionTrace;
  dictations: Dictation[];
  onViewInHistory?: (dictationId: string) => void;
}

export function FromHistoryBlock({
  trace,
  dictations,
  onViewInHistory,
}: FromHistoryBlockProps) {
  if (!trace || !showFromHistory(trace)) return null;

  const dictationById = new Map(dictations.map((d) => [d.id, d]));
  const sources = extractHistorySources(trace, dictationById);
  if (sources.length === 0) return null;

  const scrollable = sources.length > 1;

  return (
    <aside className="from-history-aside" aria-label="Source from your history">
      <div className="from-history-label">
        <HistoryIcon className="from-history-icon" />
        <span>From history</span>
        {scrollable && (
          <span className="from-history-count">{sources.length} takes</span>
        )}
      </div>
      <div
        className={`history-sources-list ${scrollable ? "history-sources-scroll" : ""}`}
      >
        {sources.map((source) => (
          <div key={source.dictationId} className="history-source-panel">
            <blockquote className="history-source-quote">
              &ldquo;{source.quote}&rdquo;
            </blockquote>
            <div className="history-source-footer">
              {source.createdAt ? (
                <span className="history-source-meta">
                  {formatDictationDate(source.createdAt)} ·{" "}
                  {formatDictationTime(source.createdAt)}
                </span>
              ) : null}
              {source.viewable && source.dictationId && onViewInHistory ? (
                <button
                  type="button"
                  className="btn-text history-source-link"
                  onClick={() => onViewInHistory(source.dictationId!)}
                >
                  View in history →
                </button>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}

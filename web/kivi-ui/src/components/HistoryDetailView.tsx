import type { Dictation } from "../types";
import { deriveTitle } from "../storage/conversations";
import { formatDictationDate, formatDictationTime } from "../utils/historyDates";

interface HistoryDetailViewProps {
  dictation: Dictation | null;
  onBack: () => void;
  onAskKivi: (dictation: Dictation) => void;
}

export function HistoryDetailView({ dictation, onBack, onAskKivi }: HistoryDetailViewProps) {
  if (!dictation) {
    return (
      <div className="history-detail">
        <p className="muted">Take not found.</p>
      </div>
    );
  }

  const text = dictation.formatted || dictation.asr;
  const title = deriveTitle(text);
  const dateStr = formatDictationDate(dictation.created_at);
  const timeStr = formatDictationTime(dictation.created_at);

  return (
    <div className="history-detail">
      <button type="button" className="back-link" onClick={onBack}>
        ← history
      </button>

      <header className="history-detail-header">
        <h2 className="page-title">{title}</h2>
        <p className="muted history-meta">
          kivi · {dateStr} · {timeStr} · dictate
        </p>
      </header>

      <section className="history-what-you-said card">
        <h3>what you said</h3>
        <blockquote>&ldquo;{text}&rdquo;</blockquote>
      </section>

      <button
        type="button"
        className="btn-secondary ask-kivi-btn"
        onClick={() => onAskKivi(dictation)}
      >
        Ask Kivi about this
      </button>
    </div>
  );
}

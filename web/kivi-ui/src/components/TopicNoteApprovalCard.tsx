import type { TopicNoteDraft, TopicNoteType } from "../types";
import { TOPIC_NOTE_TYPE_OPTIONS } from "../utils/topicNotes";

export interface TopicNoteApprovalItem extends TopicNoteDraft {
  selected: boolean;
}

interface TopicNoteApprovalCardProps {
  topicName: string;
  items: TopicNoteApprovalItem[];
  mode: "manual" | "auto";
  onTopicNameChange: (name: string) => void;
  onChangeItem: (index: number, patch: Partial<TopicNoteApprovalItem>) => void;
  onToggleItem: (index: number) => void;
  onAccept: () => void;
  onReject: () => void;
}

export function TopicNoteApprovalCard({
  topicName,
  items,
  mode,
  onTopicNameChange,
  onChangeItem,
  onToggleItem,
  onAccept,
  onReject,
}: TopicNoteApprovalCardProps) {
  const selectedCount = items.filter((i) => i.selected).length;
  const title =
    mode === "auto" && items.length > 1
      ? "Add these notes to a topic?"
      : "Add note to topic?";

  return (
    <div className="topic-approval-card reminder-card-confirm">
      <h3 className="topic-approval-title">{title}</h3>
      <label className="topic-approval-topic-label">
        Topic name
        <input
          type="text"
          className="topic-approval-topic-name"
          value={topicName}
          onChange={(e) => onTopicNameChange(e.target.value)}
          placeholder="Topic name"
        />
      </label>
      <div className="topic-approval-items">
        {items.map((item, index) => (
          <div key={`${item.sourceMessageId}-${index}`} className="topic-approval-item">
            {mode === "auto" && items.length > 1 && (
              <label className="topic-approval-check">
                <input
                  type="checkbox"
                  checked={item.selected}
                  onChange={() => onToggleItem(index)}
                />
              </label>
            )}
            <div className="topic-approval-fields">
              <label className="topic-approval-type-label">
                Type
                <select
                  value={item.type}
                  onChange={(e) =>
                    onChangeItem(index, { type: e.target.value as TopicNoteType })
                  }
                >
                  {TOPIC_NOTE_TYPE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>
              <textarea
                className="topic-approval-text"
                rows={2}
                value={item.text}
                onChange={(e) => onChangeItem(index, { text: e.target.value })}
              />
              <p className="topic-approval-source">
                Source: &ldquo;{item.sourceMessageText}&rdquo;
              </p>
            </div>
          </div>
        ))}
      </div>
      <div className="reminder-card-actions">
        <button type="button" className="reminder-action-btn" onClick={onReject}>
          Reject
        </button>
        <button
          type="button"
          className="reminder-action-btn reminder-action-primary"
          onClick={onAccept}
          disabled={selectedCount === 0 || !topicName.trim()}
        >
          Accept
        </button>
      </div>
    </div>
  );
}

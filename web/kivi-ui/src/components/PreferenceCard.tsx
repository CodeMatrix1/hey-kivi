import type { PreferenceGroup } from "../utils/lexicalGroups";

interface PreferenceCardProps {
  group: PreferenceGroup;
  onEdit: () => void;
}

export function PreferenceCard({ group, onEdit }: PreferenceCardProps) {
  return (
    <article className="preference-card card">
      <p className="pref-use">
        Use &ldquo;<strong>{group.preferred}</strong>&rdquo;
      </p>
      <p className="pref-instead muted">
        instead of {group.inputs.length} phrase{group.inputs.length === 1 ? "" : "s"}:
      </p>
      <ul className="pref-inputs">
        {group.inputs.map((input) => (
          <li key={input}>
            <span className="phrase-bullet" aria-hidden="true">·</span>
            &ldquo;{input}&rdquo;
          </li>
        ))}
      </ul>
      <button type="button" className="btn-text" onClick={onEdit}>
        Edit
      </button>
    </article>
  );
}

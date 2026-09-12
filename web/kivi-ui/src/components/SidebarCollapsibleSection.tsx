import type { ReactNode } from "react";

interface SidebarCollapsibleSectionProps {
  title: string;
  subtitle?: string;
  expanded: boolean;
  onToggle: () => void;
  addLabel: string;
  addClassName: string;
  onAdd: () => void;
  children?: ReactNode;
}

export function SidebarCollapsibleSection({
  title,
  subtitle,
  expanded,
  onToggle,
  addLabel,
  addClassName,
  onAdd,
  children,
}: SidebarCollapsibleSectionProps) {
  return (
    <section className="sidebar-panel">
      <div className="sidebar-panel-header">
        <div className="sidebar-panel-heading">
          <h2 className="sidebar-section">{title}</h2>
          {subtitle ? <span className="sidebar-panel-subtitle">{subtitle}</span> : null}
        </div>
        <button
          type="button"
          className="sidebar-panel-toggle"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-label={expanded ? `Collapse ${title}` : `Expand ${title}`}
        >
          {expanded ? "▾" : "▸"}
        </button>
      </div>

      {expanded && children}

      <button type="button" className={addClassName} onClick={onAdd}>
        {addLabel}
      </button>
    </section>
  );
}

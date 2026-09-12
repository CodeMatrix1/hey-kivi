import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { Topic } from "../types";

interface UserMessageMenuProps {
  topics: Topic[];
  open: boolean;
  onToggle: () => void;
  onSelectTopic: (topicId: string) => void;
  onCreateTopic: () => void;
}

const MENU_WIDTH = 180;

export function UserMessageMenu({
  topics,
  open,
  onToggle,
  onSelectTopic,
  onCreateTopic,
}: UserMessageMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const [menuStyle, setMenuStyle] = useState<CSSProperties | null>(null);

  useEffect(() => {
    if (!open) {
      setMenuStyle(null);
      return;
    }

    function updatePosition() {
      const btn = btnRef.current;
      if (!btn) return;
      const rect = btn.getBoundingClientRect();
      const left = Math.max(
        8,
        Math.min(rect.right - MENU_WIDTH, window.innerWidth - MENU_WIDTH - 8),
      );
      setMenuStyle({
        position: "fixed",
        top: rect.top - 8,
        left,
        transform: "translateY(-100%)",
      });
    }

    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onToggle();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open, onToggle]);

  return (
    <div className="user-message-menu-wrap" ref={menuRef}>
      <button
        ref={btnRef}
        type="button"
        className="user-message-menu-btn"
        aria-label="Message options"
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation();
          onToggle();
        }}
      >
        ⋮
      </button>
      {open && menuStyle && (
        <div className="user-message-menu user-message-menu-floating" style={menuStyle} role="menu">
          <div className="user-message-menu-label">Add to topic</div>
          {topics.length === 0 ? (
            <p className="user-message-menu-empty">No topics yet</p>
          ) : (
            topics.map((topic) => (
              <button
                key={topic.id}
                type="button"
                role="menuitem"
                onClick={() => onSelectTopic(topic.id)}
              >
                {topic.name}
              </button>
            ))
          )}
          <button type="button" role="menuitem" onClick={onCreateTopic}>
            + Create topic
          </button>
        </div>
      )}
    </div>
  );
}

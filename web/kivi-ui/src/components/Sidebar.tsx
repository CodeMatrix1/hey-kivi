import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useArrowListNav } from "../hooks/useArrowListNav";
import type { Conversation } from "../types";
import { groupConversations, polishConversationTitle } from "../utils/conversationDisplay";
import { searchConversations } from "../utils/conversationSearch";
import { SearchIcon } from "./SearchIcon";
import { SidebarCollapsibleSection } from "./SidebarCollapsibleSection";

export type NavView = "chat" | "history" | "reminders" | "personalization" | "settings";

const CONV_EXPANDED_KEY = "kivi_sidebar_conv_expanded";

function loadExpanded(): boolean {
  try {
    const raw = localStorage.getItem(CONV_EXPANDED_KEY);
    return raw === null ? true : raw === "true";
  } catch {
    return true;
  }
}

interface SidebarProps {
  conversations: Conversation[];
  activeConvId: string | null;
  activeView: NavView;
  onSelectConversation: (id: string) => void;
  onRenameConversation: (id: string, title: string) => void;
  onDeleteConversation: (id: string) => void;
  onNewChat: () => void;
}

export function Sidebar({
  conversations,
  activeConvId,
  activeView,
  onSelectConversation,
  onRenameConversation,
  onDeleteConversation,
  onNewChat,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [convExpanded, setConvExpanded] = useState(loadExpanded);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const trimmedSearch = searchQuery.trim();
  const visibleConversations = useMemo(
    () => searchConversations(conversations, searchQuery),
    [conversations, searchQuery],
  );
  const conversationGroups = useMemo(
    () => (trimmedSearch ? null : groupConversations(visibleConversations)),
    [visibleConversations, trimmedSearch],
  );

  const convNavEnabled =
    convExpanded &&
    activeView === "chat" &&
    !renamingId &&
    !menuOpenId &&
    visibleConversations.length > 0;

  const { focusIndex: convFocusIndex, setItemRef: setConvItemRef } = useArrowListNav({
    items: visibleConversations,
    enabled: convNavEnabled,
    selectedId: activeConvId,
    getId: useCallback((c: Conversation) => c.id, []),
    onSelect: onSelectConversation,
  });

  useEffect(() => {
    localStorage.setItem(CONV_EXPANDED_KEY, String(convExpanded));
  }, [convExpanded]);

  useEffect(() => {
    if (renamingId) renameInputRef.current?.focus();
  }, [renamingId]);

  useEffect(() => {
    if (!menuOpenId) return;
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpenId]);

  function startRename(conv: Conversation) {
    setMenuOpenId(null);
    setRenamingId(conv.id);
    setRenameValue(conv.title);
  }

  function commitRename(id: string) {
    const trimmed = renameValue.trim();
    setRenamingId(null);
    if (trimmed) onRenameConversation(id, trimmed);
  }

  function cancelRename() {
    setRenamingId(null);
    setRenameValue("");
  }

  function handleDeleteConv(id: string) {
    setMenuOpenId(null);
    if (window.confirm("Delete this conversation?")) {
      onDeleteConversation(id);
    }
  }

  function renderConversationRow(c: Conversation, index: number) {
    const isActive = activeConvId === c.id && activeView === "chat";
    const isKeyboardFocus = convFocusIndex === index;
    const isRenaming = renamingId === c.id;
    const displayTitle = polishConversationTitle(c.title);

    return (
      <div
        key={c.id}
        className={`sidebar-conv-row ${isActive ? "active" : ""} ${isKeyboardFocus ? "keyboard-focus" : ""}`}
        ref={(el) => {
          setConvItemRef(index)(el);
          if (menuOpenId === c.id) menuRef.current = el;
        }}
        role="option"
        aria-selected={isActive}
      >
        {isRenaming ? (
          <input
            ref={renameInputRef}
            type="text"
            className="sidebar-rename-input"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onBlur={() => commitRename(c.id)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                commitRename(c.id);
              } else if (e.key === "Escape") {
                e.preventDefault();
                cancelRename();
              }
            }}
          />
        ) : (
          <button
            type="button"
            className={`sidebar-item ${isActive ? "active" : ""}`}
            onClick={() => onSelectConversation(c.id)}
          >
            <span className="sidebar-item-title">{displayTitle}</span>
          </button>
        )}
        {!isRenaming && (
          <div className="sidebar-conv-menu-wrap">
            <button
              type="button"
              className="sidebar-conv-menu-btn"
              aria-label="Conversation options"
              aria-expanded={menuOpenId === c.id}
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpenId(menuOpenId === c.id ? null : c.id);
              }}
            >
              ⋯
            </button>
            {menuOpenId === c.id && (
              <div className="sidebar-conv-menu" role="menu">
                <button type="button" role="menuitem" onClick={() => startRename(c)}>
                  Rename
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="sidebar-conv-menu-delete"
                  onClick={() => handleDeleteConv(c.id)}
                >
                  Delete
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1 className="brand">kivi</h1>
      </div>

      <SidebarCollapsibleSection
        title="conversations"
        expanded={convExpanded}
        onToggle={() => setConvExpanded((v) => !v)}
        addLabel="+ New conversation"
        addClassName="btn-new-conversation"
        onAdd={onNewChat}
      >
        {conversations.length > 0 && (
          <label className="sidebar-search-field">
            <SearchIcon className="sidebar-search-icon" />
            <span className="sr-only">Search conversations</span>
            <input
              type="search"
              className="sidebar-search-input"
              placeholder="Search conversations…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </label>
        )}

        {conversations.length === 0 ? (
          <p className="sidebar-empty">No conversations yet</p>
        ) : trimmedSearch && visibleConversations.length === 0 ? (
          <p className="sidebar-empty">No conversations found</p>
        ) : (
          <div className="sidebar-conv-list" role="listbox" aria-label="Conversations">
            {conversationGroups
              ? (() => {
                  let index = 0;
                  return conversationGroups.map((group) => (
                    <div key={group.label} className="sidebar-conv-group">
                      <div className="sidebar-group-label">{group.label}</div>
                      {group.conversations.map((c) => {
                        const row = renderConversationRow(c, index);
                        index += 1;
                        return row;
                      })}
                    </div>
                  ));
                })()
              : visibleConversations.map((c, index) => renderConversationRow(c, index))}
          </div>
        )}
      </SidebarCollapsibleSection>
    </aside>
  );
}

import { CONVERSATIONS_STORAGE_KEY } from "../storage/conversations";

interface SettingsViewProps {
  userId: string;
  userName?: string;
  conversationCount: number;
  demoChatsLoading?: boolean;
  demoChatsMessage?: string | null;
  onUserIdChange: (id: string) => void;
  onOpenDeveloper: () => void;
  onLoadDemoChats: () => void;
  onClearConversations: () => void;
}

export function SettingsView({
  userId,
  userName,
  conversationCount,
  demoChatsLoading = false,
  demoChatsMessage,
  onUserIdChange,
  onOpenDeveloper,
  onLoadDemoChats,
  onClearConversations,
}: SettingsViewProps) {
  return (
    <div className="settings-view">
      <header className="page-header">
        <h2 className="page-title">settings</h2>
      </header>

      <section className="card">
        <h3>Profile</h3>
        {userName && <p>Display name: <strong>{userName}</strong></p>}
        <label className="field">
          User ID
          <input
            type="text"
            value={userId}
            onChange={(e) => onUserIdChange(e.target.value.trim())}
            spellCheck={false}
          />
        </label>
        <p className="muted small">Used for memory and dictation lookup.</p>
      </section>

      <section className="card">
        <h3>Conversations</h3>
        <p className="muted small">
          Chats are stored in your browser only (localStorage key{" "}
          <code className="storage-key">{CONVERSATIONS_STORAGE_KEY}</code>). They are not
          saved on the server and will not sync across devices.
        </p>
        <p className="muted small">
          {conversationCount === 0
            ? "No conversations saved."
            : `${conversationCount} conversation${conversationCount === 1 ? "" : "s"} saved.`}
        </p>
        <p className="muted small">
          Demo threads load from{" "}
          <code className="storage-key">web/assets/demo_chats.json</code> (see{" "}
          <code className="storage-key">DEMO_CHATS.md</code> for the schema).
        </p>
        {demoChatsMessage && <p className="settings-flash">{demoChatsMessage}</p>}
        <div className="settings-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={onLoadDemoChats}
            disabled={demoChatsLoading}
          >
            {demoChatsLoading ? "Loading demo chats…" : "Load demo chats"}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={onClearConversations}
            disabled={conversationCount === 0}
          >
            Clear all conversations
          </button>
        </div>
      </section>

      <section className="card">
        <h3>Developer</h3>
        <p className="muted">Query library, decision traces, and per-turn metrics.</p>
        <button type="button" className="btn-secondary" onClick={onOpenDeveloper}>
          Open developer tools →
        </button>
      </section>
    </div>
  );
}

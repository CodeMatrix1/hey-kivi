import { useCallback, useEffect, useRef, useState } from "react";
import {
  createTextDictation,
  getDemoChatsFile,
  getDictations,
  getHealth,
  getQueryCases,
} from "./api/client";
import { ChatView } from "./components/ChatView";
import { DeveloperTools } from "./components/DeveloperTools";
import { HistoryDetailView } from "./components/HistoryDetailView";
import { HistoryView } from "./components/HistoryView";
import { PersonalizationView } from "./components/PersonalizationView";
import { ReminderRail } from "./components/ReminderRail";
import { ReminderToast } from "./components/ReminderToast";
import { RemindersView } from "./components/RemindersView";
import { SettingsView } from "./components/SettingsView";
import { TopicView } from "./components/TopicView";
import { AppNav } from "./components/AppNav";
import { Sidebar, type NavView } from "./components/Sidebar";
import { useReminderChecker } from "./hooks/useReminderChecker";
import {
  clearAllConversations,
  deleteConversation,
  listConversations,
  renameConversation,
} from "./storage/conversations";
import { loadAndImportDemoChats } from "./storage/demoChats";
import { deleteReminder, listReminders } from "./storage/reminders";
import {
  clearAllTopics,
  createTopic,
  deleteTopic,
  getTopic,
  listTopics,
  updateTopicName,
} from "./storage/topics";
import type {
  AppView,
  Conversation,
  Dictation,
  PendingDictationContext,
  QueryCase,
  Topic,
} from "./types";

const USER_ID_KEY = "kivi_user_id_v1";

function toNavView(view: AppView): NavView {
  if (view === "history" || view === "historyDetail") return "history";
  if (view === "reminders") return "reminders";
  if (view === "personalization") return "personalization";
  if (view === "settings" || view === "developer") return "settings";
  return "chat";
}

export default function App() {
  const [view, setView] = useState<AppView>("chat");
  const [userId, setUserId] = useState(() => localStorage.getItem(USER_ID_KEY) || "");
  const [userName, setUserName] = useState<string>();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [dictations, setDictations] = useState<Dictation[]>([]);
  const [dictationCount, setDictationCount] = useState(0);
  const [dictationReturned, setDictationReturned] = useState(0);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [queryCases, setQueryCases] = useState<QueryCase[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [activeTopicId, setActiveTopicId] = useState<string | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [chatScrollToMessageId, setChatScrollToMessageId] = useState<string | null>(
    null,
  );
  const [activeReminderId, setActiveReminderId] = useState<string | null>(null);
  const [reminders, setReminders] = useState(() => listReminders());
  const [showAddReminder, setShowAddReminder] = useState(false);
  const [activeDictationId, setActiveDictationId] = useState<string | null>(null);
  const [chatPrefill, setChatPrefill] = useState("");
  const [pendingDictation, setPendingDictation] = useState<PendingDictationContext | null>(
    null,
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [demoChatsMessage, setDemoChatsMessage] = useState<string | null>(null);
  const [demoChatsLoading, setDemoChatsLoading] = useState(false);
  const { activeToast, tick, reload, dismissToast } = useReminderChecker();
  const demoChatsBootstrapped = useRef(false);

  const refreshConversations = useCallback(() => {
    setConversations(listConversations());
  }, []);

  const refreshTopics = useCallback(() => {
    setTopics(listTopics());
  }, []);

  const refreshReminders = useCallback(() => {
    setReminders(listReminders());
  }, []);

  const loadHistory = useCallback(async () => {
    if (!userId) return;
    setHistoryLoading(true);
    try {
      const data = await getDictations(userId, 500);
      setDictations(data.dictations || []);
      setDictationCount(data.count ?? 0);
      setDictationReturned(data.returned ?? data.dictations?.length ?? 0);
    } catch {
      setDictations([]);
      setDictationCount(0);
      setDictationReturned(0);
    } finally {
      setHistoryLoading(false);
    }
  }, [userId]);

  const runDemoChatsImport = useCallback(
    async (mode: "replace_empty" | "merge") => {
      setDemoChatsLoading(true);
      setDemoChatsMessage(null);
      try {
        const result = await loadAndImportDemoChats(getDemoChatsFile, mode);
        refreshConversations();
        refreshTopics();
        const parts: string[] = [];
        if (result.imported > 0) {
          parts.push(
            `${result.imported} chat${result.imported === 1 ? "" : "s"}`,
          );
        }
        if (result.topicsImported > 0) {
          parts.push(
            `${result.topicsImported} topic${result.topicsImported === 1 ? "" : "s"}`,
          );
        }
        if (parts.length > 0) {
          const skipped =
            result.skipped + result.topicsSkipped > 0
              ? ` (${result.skipped + result.topicsSkipped} skipped)`
              : "";
          setDemoChatsMessage(`Loaded ${parts.join(" and ")}${skipped}.`);
        } else if (result.skipped === 0 && result.topicsSkipped === 0) {
          setDemoChatsMessage("Demo seed file has no conversations or topics yet.");
        } else {
          setDemoChatsMessage(
            mode === "replace_empty"
              ? "Skipped — you already have conversations or topics saved."
              : "No new demo data imported (already present).",
          );
        }
        return result;
      } catch {
        setDemoChatsMessage("Could not load demo chats. Check demo_chats.json.");
        return null;
      } finally {
        setDemoChatsLoading(false);
      }
    },
    [refreshConversations, refreshTopics],
  );

  useEffect(() => {
    refreshConversations();
    refreshTopics();
    refreshReminders();
    getQueryCases()
      .then(setQueryCases)
      .catch(() => setQueryCases([]));

    getHealth()
      .then((h) => {
        if (!userId) setUserId(h.default_user_id);
        setUserName(h.default_user_name);
      })
      .catch(() => setApiError("Could not reach Kivi server"));

    const params = new URLSearchParams(window.location.search);
    if (params.get("dev") === "1") setView("developer");
  }, []);

  useEffect(() => {
    if (demoChatsBootstrapped.current) return;
    demoChatsBootstrapped.current = true;
    const params = new URLSearchParams(window.location.search);
    const seedMode = params.get("seed_chats") === "1" ? "merge" : "replace_empty";
    void runDemoChatsImport(seedMode);
  }, [runDemoChatsImport]);

  useEffect(() => {
    if (userId) localStorage.setItem(USER_ID_KEY, userId);
  }, [userId]);

  useEffect(() => {
    if (userId) loadHistory();
  }, [userId, loadHistory]);

  useEffect(() => {
    refreshReminders();
  }, [tick, refreshReminders]);

  const activeDictation =
    dictations.find((d) => d.id === activeDictationId) || null;

  function handleNewChat() {
    setActiveConvId(null);
    setActiveTopicId(null);
    setActiveReminderId(null);
    setChatPrefill("");
    setPendingDictation(null);
    setChatScrollToMessageId(null);
    setView("chat");
    setSidebarOpen(false);
  }

  function handleNewReminder() {
    setActiveReminderId(null);
    setShowAddReminder(true);
    setView("reminders");
    setSidebarOpen(false);
  }

  function handleSelectReminder(id: string) {
    setActiveReminderId(id);
    setShowAddReminder(false);
    setView("reminders");
    setSidebarOpen(false);
  }

  function handleDeleteReminder(id: string) {
    if (!deleteReminder(id)) return;
    if (activeReminderId === id) setActiveReminderId(null);
    refreshReminders();
    reload();
  }

  function handleSelectConversation(id: string) {
    setActiveConvId(id);
    setActiveTopicId(null);
    setPendingDictation(null);
    setChatPrefill("");
    setChatScrollToMessageId(null);
    setView("chat");
    setSidebarOpen(false);
  }

  function handleSelectTopic(id: string) {
    setActiveTopicId(id);
    setView("topic");
    setSidebarOpen(false);
  }

  function handleNewTopic() {
    const name = window.prompt("Topic name");
    if (!name?.trim()) return;
    try {
      const topic = createTopic(name);
      refreshTopics();
      handleSelectTopic(topic.id);
    } catch {
      // empty name — ignore
    }
  }

  function handleOpenSourceMessage(conversationId: string, messageId: string) {
    setActiveConvId(conversationId);
    setActiveTopicId(null);
    setChatScrollToMessageId(messageId);
    setView("chat");
    setSidebarOpen(false);
  }

  function handleNavigate(nav: NavView) {
    if (nav === "chat") {
      setView("chat");
    } else if (nav === "history") {
      setActiveDictationId(null);
      setView("history");
    } else if (nav === "reminders") {
      setView("reminders");
    } else if (nav === "personalization") {
      setView("personalization");
    } else if (nav === "settings") {
      setView("settings");
    }
    setSidebarOpen(false);
  }

  function handleAskKivi(dictation: Dictation) {
    setActiveConvId(null);
    setPendingDictation({
      formatted: dictation.formatted,
      asr: dictation.asr,
    });
    setChatPrefill("What can you tell me about this?");
    setView("chat");
  }

  function handleTryQuery(message: string) {
    setActiveConvId(null);
    setPendingDictation(null);
    setChatPrefill(message);
    setView("chat");
  }

  function handleViewInHistory(dictationId: string) {
    setActiveDictationId(dictationId);
    setView("historyDetail");
    setSidebarOpen(false);
  }

  function handleRenameConversation(id: string, title: string) {
    renameConversation(id, title);
    refreshConversations();
  }

  function handleDeleteConversation(id: string) {
    if (!deleteConversation(id)) return;
    if (activeConvId === id) setActiveConvId(null);
    refreshConversations();
  }

  function handleRenameTopic(id: string, name: string) {
    updateTopicName(id, name);
    refreshTopics();
  }

  function handleDeleteTopic(id: string) {
    if (!deleteTopic(id)) return;
    if (activeTopicId === id) {
      setActiveTopicId(null);
      setView("chat");
    }
    refreshTopics();
  }

  const navView = toNavView(view);

  return (
    <div className="app-shell">
      <button
        type="button"
        className="mobile-menu-btn"
        onClick={() => setSidebarOpen((o) => !o)}
        aria-label="Toggle sidebar"
      >
        ☰
      </button>

      <div className={`sidebar-overlay ${sidebarOpen ? "open" : ""}`}>
        <Sidebar
          conversations={conversations}
          topics={topics}
          activeConvId={activeConvId}
          activeTopicId={activeTopicId}
          activeView={navView}
          topicViewActive={view === "topic"}
          onSelectConversation={handleSelectConversation}
          onRenameConversation={handleRenameConversation}
          onDeleteConversation={handleDeleteConversation}
          onNewChat={handleNewChat}
          onSelectTopic={handleSelectTopic}
          onRenameTopic={handleRenameTopic}
          onDeleteTopic={handleDeleteTopic}
          onNewTopic={handleNewTopic}
        />
      </div>

      <main className="main-panel">
        {apiError && (
          <div className="error-banner top-banner">
            {apiError}
            <button type="button" onClick={() => window.location.reload()}>Retry</button>
          </div>
        )}

        {view === "chat" && (
          <ChatView
            userId={userId}
            conversationId={activeConvId}
            conversations={conversations}
            topics={topics}
            dictations={dictations}
            prefill={chatPrefill}
            pendingDictation={pendingDictation}
            scrollToMessageId={chatScrollToMessageId}
            onConversationCreated={(id) => {
              setActiveConvId(id);
              refreshConversations();
            }}
            onConversationUpdated={refreshConversations}
            onTopicsUpdated={refreshTopics}
            onPendingDictationConsumed={() => setPendingDictation(null)}
            onViewInHistory={handleViewInHistory}
            onScrollToMessageConsumed={() => setChatScrollToMessageId(null)}
            onReminderCreated={() => {
              refreshReminders();
              reload();
            }}
          />
        )}

        {view === "topic" && activeTopicId && (() => {
          const activeTopic =
            getTopic(activeTopicId) ?? topics.find((t) => t.id === activeTopicId);
          if (!activeTopic) return null;
          return (
            <TopicView
              topic={activeTopic}
              onBack={() => {
                setActiveTopicId(null);
                setView("chat");
              }}
              onOpenSource={handleOpenSourceMessage}
              onOpenConversation={handleSelectConversation}
              onTopicsUpdated={refreshTopics}
            />
          );
        })()}

        {view === "reminders" && (
          <RemindersView
            tick={tick}
            selectedId={activeReminderId}
            showAdd={showAddReminder}
            onSelectedIdChange={setActiveReminderId}
            onShowAddChange={setShowAddReminder}
            onReload={() => {
              reload();
              refreshReminders();
            }}
            onViewConversation={(id) => {
              setActiveConvId(id);
              setView("chat");
            }}
          />
        )}

        {view === "history" && (
          <HistoryView
            dictations={dictations}
            totalCount={dictationCount}
            returnedCount={dictationReturned}
            loading={historyLoading}
            onSelect={(id) => {
              setActiveDictationId(id);
              setView("historyDetail");
            }}
            onAddNote={async (text) => {
              if (!userId) return;
              await createTextDictation(userId, text);
              await loadHistory();
            }}
          />
        )}

        {view === "historyDetail" && (
          <HistoryDetailView
            dictation={activeDictation}
            onBack={() => {
              setActiveDictationId(null);
              setView("history");
            }}
            onAskKivi={handleAskKivi}
          />
        )}

        {view === "personalization" && <PersonalizationView userId={userId} />}

        {view === "settings" && (
          <SettingsView
            userId={userId}
            userName={userName}
            conversationCount={conversations.length}
            topicCount={topics.length}
            onUserIdChange={setUserId}
            demoChatsLoading={demoChatsLoading}
            demoChatsMessage={demoChatsMessage}
            onOpenDeveloper={() => setView("developer")}
            onLoadDemoChats={() => void runDemoChatsImport("merge")}
            onClearConversations={() => {
              clearAllConversations();
              clearAllTopics();
              setActiveConvId(null);
              setActiveTopicId(null);
              refreshConversations();
              refreshTopics();
            }}
          />
        )}

        {view === "developer" && (
          <DeveloperTools
            queryCases={queryCases}
            conversations={conversations}
            activeConvId={activeConvId}
            onTryQuery={handleTryQuery}
          />
        )}
      </main>

      <div className="right-rail">
        <ReminderRail
          reminders={reminders}
          tick={tick}
          activeReminderId={activeReminderId}
          remindersViewActive={view === "reminders"}
          onSelectReminder={handleSelectReminder}
          onDeleteReminder={(id) => {
            if (!window.confirm("Delete this reminder?")) return;
            handleDeleteReminder(id);
          }}
          onNewReminder={handleNewReminder}
        />
        <AppNav activeView={navView} onNavigate={handleNavigate} />
      </div>

      {activeToast && (
        <div className="reminder-toast-container">
          <ReminderToast
            reminder={activeToast}
            onDismiss={() => {
              handleDeleteReminder(activeToast.id);
              dismissToast();
            }}
          />
        </div>
      )}
    </div>
  );
}

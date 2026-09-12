import type { NavView } from "./Sidebar";
import {
  ChatNavIcon,
  HistoryNavIcon,
  PersonalizationNavIcon,
  RemindersNavIcon,
  SettingsNavIcon,
} from "./NavIcons";

interface AppNavProps {
  activeView: NavView;
  onNavigate: (view: NavView) => void;
  className?: string;
}

const NAV_ITEMS: Array<{
  view: NavView;
  label: string;
  Icon: typeof ChatNavIcon;
}> = [
  { view: "chat", label: "Chat", Icon: ChatNavIcon },
  { view: "history", label: "History", Icon: HistoryNavIcon },
  { view: "reminders", label: "Reminders", Icon: RemindersNavIcon },
  { view: "personalization", label: "Personalize", Icon: PersonalizationNavIcon },
  { view: "settings", label: "Settings", Icon: SettingsNavIcon },
];

export function AppNav({ activeView, onNavigate, className = "" }: AppNavProps) {
  return (
    <nav className={`app-nav ${className}`.trim()} aria-label="App navigation">
      {NAV_ITEMS.map(({ view, label, Icon }) => (
        <button
          key={view}
          type="button"
          className={`app-nav-link ${activeView === view ? "active" : ""}`}
          onClick={() => onNavigate(view)}
          aria-current={activeView === view ? "page" : undefined}
        >
          <Icon className="app-nav-icon" />
          <span className="app-nav-label">{label}</span>
        </button>
      ))}
    </nav>
  );
}

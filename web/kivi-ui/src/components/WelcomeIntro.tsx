const FEATURES = [
  {
    title: "Recall",
    detail: "Ask what you've shared — people, trips, work, preferences.",
  },
  {
    title: "History",
    detail: "Browse past notes or add a text entry anytime.",
  },
  {
    title: "Prepare",
    detail: "Find a note and polish it for a meeting or update.",
  },
  {
    title: "Reminders",
    detail:
      'Include remind plus today, tomorrow, a date, or a time — e.g. "remind me tomorrow at 8pm to call Maya." I\'ll confirm before saving; upcoming ones show in the sidebar.',
  },
] as const;

export function WelcomeIntro() {
  return (
    <header className="welcome-intro">
      <h2 className="page-title">What can I help you with?</h2>
      <p className="welcome-lead">
        I keep your chats and note history connected — recall details, prep for meetings,
        and pick up where you left off. Spelling and phrasing live under{" "}
        <span className="welcome-em">personalization</span>.
      </p>
      <ul className="welcome-features">
        {FEATURES.map((f) => (
          <li key={f.title} className="welcome-feature">
            <strong>{f.title}</strong>
            <span>{f.detail}</span>
          </li>
        ))}
      </ul>
    </header>
  );
}

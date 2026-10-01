export type ViewKey = "pipeline" | "events" | "entities" | "decisions";

const TABS: { key: ViewKey; label: string }[] = [
  { key: "pipeline", label: "Pipeline Health" },
  { key: "events", label: "Event Stream" },
  { key: "entities", label: "Entity State" },
  { key: "decisions", label: "Agent Decisions" },
];

export function NavBar({
  active,
  onChange,
  connected,
}: {
  active: ViewKey;
  onChange: (key: ViewKey) => void;
  connected: boolean;
}) {
  return (
    <header className="nav-bar">
      <div className="nav-bar__brand">
        <span className="nav-bar__title">Semantic Data Pipeline</span>
        <span className={`nav-bar__status ${connected ? "nav-bar__status--live" : "nav-bar__status--down"}`}>
          <span className="nav-bar__status-dot" />
          {connected ? "live" : "reconnecting"}
        </span>
      </div>
      <nav className="nav-bar__tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`nav-bar__tab ${active === tab.key ? "nav-bar__tab--active" : ""}`}
            onClick={() => onChange(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </nav>
    </header>
  );
}

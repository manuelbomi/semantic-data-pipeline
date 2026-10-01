import { useState } from "react";
import { NavBar } from "./components/NavBar";
import type { ViewKey } from "./components/NavBar";
import { LiveStoreProvider, useLiveStore } from "./api/useLiveStore";
import { PipelineHealthView } from "./views/PipelineHealthView";
import { EventStreamView } from "./views/EventStreamView";
import { EntityStateView } from "./views/EntityStateView";
import { AgentDecisionView } from "./views/AgentDecisionView";

function Shell() {
  const [view, setView] = useState<ViewKey>("decisions");
  const { connected } = useLiveStore();

  return (
    <div className="app-shell">
      <NavBar active={view} onChange={setView} connected={connected} />
      <main className="app-shell__content">
        {view === "pipeline" && <PipelineHealthView />}
        {view === "events" && <EventStreamView />}
        {view === "entities" && <EntityStateView />}
        {view === "decisions" && <AgentDecisionView />}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <LiveStoreProvider>
      <Shell />
    </LiveStoreProvider>
  );
}

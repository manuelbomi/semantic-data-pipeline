import { useState } from "react";
import { api } from "../api/client";
import type { EventTrace } from "../api/types";
import { useLiveStore } from "../api/useLiveStore";

const STAGE_KEYS: { key: keyof EventTrace; label: string }[] = [
  { key: "raw", label: "1. Raw (as the source sent it)" },
  { key: "normalized", label: "2. Normalized (consistent field names/units)" },
  { key: "linked", label: "3. Entity-linked (resolved to a canonical id)" },
  { key: "enriched", label: "4. Enriched (dependency + deploy context attached)" },
];

export function EventStreamView() {
  const { events } = useLiveStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [trace, setTrace] = useState<EventTrace | null>(null);
  const [loading, setLoading] = useState(false);

  async function selectEvent(eventId: string) {
    setSelectedId(eventId);
    setLoading(true);
    try {
      const t = await api.getEventTrace(eventId);
      setTrace(t);
    } catch {
      setTrace(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="view">
      <h2 className="view__title">Event Stream</h2>
      <p className="view__subtitle">
        Raw events from three simulated sources, moving through the pipeline live. Click one to see exactly how it was
        transformed at each stage.
      </p>

      <div className="event-stream">
        <div className="event-stream__list">
          {events.length === 0 && <div className="empty-state">Waiting for events...</div>}
          {events.map((e) => (
            <button
              key={e.event_id}
              className={`event-row ${selectedId === e.event_id ? "event-row--selected" : ""}`}
              onClick={() => selectEvent(e.event_id)}
            >
              <span className={`event-row__kind event-row__kind--${e.kind}`}>{e.kind}</span>
              <span className="event-row__source">{e.source}</span>
              <span className="event-row__ref">{e.entity_ref ?? "-"}</span>
              <span className="event-row__canonical">
                {e.canonical_id ?? <em className="event-row__unresolved">unresolved</em>}
              </span>
            </button>
          ))}
        </div>

        <div className="event-stream__detail">
          {!selectedId && <div className="empty-state">Select an event to see its full trace.</div>}
          {selectedId && loading && <div className="empty-state">Loading trace...</div>}
          {selectedId && !loading && trace && (
            <div className="trace-panels">
              {STAGE_KEYS.map(({ key, label }) => (
                <div className="trace-panel" key={key}>
                  <h4 className="trace-panel__title">{label}</h4>
                  {trace[key] ? (
                    <pre className="trace-panel__body">{JSON.stringify(trace[key], null, 2)}</pre>
                  ) : (
                    <div className="trace-panel__missing">not reached yet</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

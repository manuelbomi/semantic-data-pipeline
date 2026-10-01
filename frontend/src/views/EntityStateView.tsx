import { useMemo, useState } from "react";
import { useLiveStore } from "../api/useLiveStore";
import { HealthBadge } from "../components/HealthBadge";

function formatAge(epochSeconds: number): string {
  const seconds = Math.max(0, Math.round(Date.now() / 1000 - epochSeconds));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  return `${minutes}m ago`;
}

export function EntityStateView() {
  const { entities } = useLiveStore();
  const list = useMemo(() => Object.values(entities).sort((a, b) => a.entity_id.localeCompare(b.entity_id)), [entities]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selected = selectedId ? entities[selectedId] : list[0];

  return (
    <div className="view">
      <h2 className="view__title">Entity State</h2>
      <p className="view__subtitle">
        The current, reconciled view of every known entity - this is what the semantic layer actually serves to
        anything downstream that needs to make a decision.
      </p>

      <div className="entity-state">
        <div className="entity-state__list">
          {list.map((e) => (
            <button
              key={e.entity_id}
              className={`entity-row ${selected?.entity_id === e.entity_id ? "entity-row--selected" : ""}`}
              onClick={() => setSelectedId(e.entity_id)}
            >
              <div className="entity-row__name">{e.canonical_name}</div>
              <div className="entity-row__type">{e.entity_type}</div>
              <HealthBadge health={e.health} />
            </button>
          ))}
          {list.length === 0 && <div className="empty-state">Waiting for entity data...</div>}
        </div>

        <div className="entity-state__detail">
          {!selected && <div className="empty-state">Select an entity to see its full state.</div>}
          {selected && (
            <>
              <div className="entity-detail__header">
                <h3>{selected.canonical_name}</h3>
                <HealthBadge health={selected.health} />
              </div>
              <div className="entity-detail__id">{selected.entity_id}</div>

              {selected.last_metric && (
                <div className="entity-detail__metrics">
                  {Object.entries(selected.last_metric).map(([k, v]) => (
                    <StatPair key={k} label={k} value={v} />
                  ))}
                </div>
              )}

              <div className="entity-detail__section">
                <h4>Dependency context</h4>
                <p className="entity-detail__dep-line">
                  <strong>Depends on:</strong>{" "}
                  {selected.dependency_context.depends_on.length > 0
                    ? selected.dependency_context.depends_on.join(", ")
                    : "nothing"}
                </p>
                <p className="entity-detail__dep-line">
                  <strong>Depended on by:</strong>{" "}
                  {selected.dependency_context.depended_on_by.length > 0
                    ? selected.dependency_context.depended_on_by.join(", ")
                    : "nothing"}
                </p>
              </div>

              <div className="entity-detail__section">
                <h4>Recent deploys</h4>
                {selected.recent_deploys.length === 0 && <p className="empty-state">No deploys in the recency window.</p>}
                {selected.recent_deploys.map((d) => (
                  <div className="deploy-row" key={d.deployed_at}>
                    <span className="deploy-row__version">{d.version}</span>
                    <span className="deploy-row__age">{formatAge(d.deployed_at)}</span>
                  </div>
                ))}
              </div>

              <div className="entity-detail__section">
                <h4>Recent events (incident history)</h4>
                {selected.recent_events
                  .slice()
                  .reverse()
                  .map((ev) => (
                    <div className="incident-row" key={ev.event_id}>
                      <span className={`event-row__kind event-row__kind--${ev.kind}`}>{ev.kind}</span>
                      <span className="incident-row__source">{ev.source}</span>
                      <span className="incident-row__age">{formatAge(ev.received_at)}</span>
                    </div>
                  ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function StatPair({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat-pair">
      <span className="stat-pair__label">{label}</span>
      <span className="stat-pair__value">{value}</span>
    </div>
  );
}

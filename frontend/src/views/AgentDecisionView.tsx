import { useState } from "react";
import { useLiveStore } from "../api/useLiveStore";
import type { Decision } from "../api/types";

const ACTION_LABELS: Record<Decision["action"], string> = {
  rollback: "Rollback",
  investigate_dependency: "Investigate dependency",
  restart: "Restart",
};

function timeAgo(epochSeconds: number): string {
  const seconds = Math.max(0, Math.round(Date.now() / 1000 - epochSeconds));
  if (seconds < 60) return `${seconds}s ago`;
  return `${Math.round(seconds / 60)}m ago`;
}

export function AgentDecisionView() {
  const { decisions } = useLiveStore();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="view">
      <h2 className="view__title">Agent Decisions</h2>
      <p className="view__subtitle">
        A small rule-based agent polls the semantic layer every few seconds and decides what to do about anything
        unhealthy. Every decision below is backed by the exact facts it read and the rule that fired - nothing here is
        a black box.
      </p>

      <div className="decision-list">
        {decisions.length === 0 && (
          <div className="empty-state">No decisions yet. Everything is currently healthy, or the agent hasn't polled yet.</div>
        )}
        {decisions.map((d) => {
          const expanded = expandedId === d.decision_id;
          return (
            <div className="decision-card" key={d.decision_id}>
              <button className="decision-card__header" onClick={() => setExpandedId(expanded ? null : d.decision_id)}>
                <span className={`decision-card__action decision-card__action--${d.action}`}>{ACTION_LABELS[d.action]}</span>
                <span className="decision-card__entity">{d.entity_id}</span>
                <span className="decision-card__time">{timeAgo(d.created_at)}</span>
                <span className="decision-card__chevron">{expanded ? "−" : "+"}</span>
              </button>
              <p className="decision-card__reasoning">{d.reasoning}</p>
              {expanded && (
                <div className="decision-card__facts">
                  <h4>Facts the agent used</h4>
                  <pre>{JSON.stringify(d.facts, null, 2)}</pre>
                  <div className="decision-card__rule">
                    rule fired: <code>{d.rule}</code>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

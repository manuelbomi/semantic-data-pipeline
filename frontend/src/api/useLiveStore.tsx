import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api } from "./client";
import type { Decision, EntityState, EventTraceSummary, PipelineMetrics, WsMessage } from "./types";

const MAX_DECISIONS = 100;
const MAX_EVENTS = 150;
const MAX_METRICS_HISTORY = 60;

export interface MetricsSample {
  timestamp: number;
  metrics: PipelineMetrics;
}

interface LiveStore {
  entities: Record<string, EntityState>;
  decisions: Decision[];
  events: EventTraceSummary[];
  metricsLatest: PipelineMetrics | null;
  metricsHistory: MetricsSample[];
  connected: boolean;
}

const LiveStoreContext = createContext<LiveStore | null>(null);

export function useLiveStore(): LiveStore {
  const ctx = useContext(LiveStoreContext);
  if (!ctx) {
    throw new Error("useLiveStore must be used inside <LiveStoreProvider>");
  }
  return ctx;
}

export function LiveStoreProvider({ children }: { children: ReactNode }) {
  const [entities, setEntities] = useState<Record<string, EntityState>>({});
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [events, setEvents] = useState<EventTraceSummary[]>([]);
  const [metricsLatest, setMetricsLatest] = useState<PipelineMetrics | null>(null);
  const [metricsHistory, setMetricsHistory] = useState<MetricsSample[]>([]);
  const [connected, setConnected] = useState(false);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // One-time initial load: fetch the full state of every known entity,
  // the decisions/events made so far, and the current metrics snapshot.
  // After this, the WebSocket below takes over for live updates - we
  // don't poll REST endpoints on an interval.
  useEffect(() => {
    let cancelled = false;

    async function loadInitial() {
      try {
        const summaries = await api.listEntities();
        const states = await Promise.all(summaries.map((s) => api.getEntityState(s.entity_id)));
        if (cancelled) return;
        const byId: Record<string, EntityState> = {};
        for (const state of states) byId[state.entity_id] = state;
        setEntities(byId);
      } catch {
        // The backend may not be up yet on first paint; the WebSocket
        // reconnect loop below will eventually bring everything current.
      }

      try {
        const [decisionList, eventList, metrics] = await Promise.all([
          api.getAgentDecisions(MAX_DECISIONS),
          api.getRecentEvents(MAX_EVENTS),
          api.getPipelineMetrics(),
        ]);
        if (cancelled) return;
        setDecisions(decisionList);
        setEvents(eventList);
        setMetricsLatest(metrics);
      } catch {
        // Same reasoning as above.
      }
    }

    loadInitial();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let cancelled = false;

    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          reconnectTimer.current = setTimeout(connect, 2000);
        }
      };
      ws.onerror = () => ws?.close();

      ws.onmessage = (ev) => {
        const message = JSON.parse(ev.data) as WsMessage;
        if (message.type === "entity_update") {
          setEntities((prev) => ({ ...prev, [message.data.entity_id]: message.data }));
        } else if (message.type === "decision") {
          setDecisions((prev) => [message.data, ...prev].slice(0, MAX_DECISIONS));
        } else if (message.type === "event") {
          const summary: EventTraceSummary = {
            event_id: message.data.event_id,
            source: message.data.source,
            kind: message.data.kind,
            entity_ref: message.data.entity_ref,
            canonical_id: message.data.canonical_id,
            complete: true,
          };
          setEvents((prev) => [summary, ...prev].slice(0, MAX_EVENTS));
        } else if (message.type === "metrics") {
          setMetricsLatest(message.data);
          setMetricsHistory((prev) => [...prev, { timestamp: Date.now(), metrics: message.data }].slice(-MAX_METRICS_HISTORY));
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      ws?.close();
    };
  }, []);

  const value = useMemo<LiveStore>(
    () => ({ entities, decisions, events, metricsLatest, metricsHistory, connected }),
    [entities, decisions, events, metricsLatest, metricsHistory, connected]
  );

  return <LiveStoreContext.Provider value={value}>{children}</LiveStoreContext.Provider>;
}

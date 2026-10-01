import type {
  Decision,
  EntitySummary,
  EntityState,
  EventTrace,
  EventTraceSummary,
  PipelineMetrics,
} from "./types";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`GET ${path} failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

async function postJSON<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error(`POST ${path} failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export const api = {
  listEntities: () => getJSON<EntitySummary[]>("/api/entities"),
  getEntityState: (id: string) => getJSON<EntityState>(`/api/entities/${encodeURIComponent(id)}/state`),
  getPipelineMetrics: () => getJSON<PipelineMetrics>("/api/metrics/pipeline"),
  getAgentDecisions: (limit = 50) => getJSON<Decision[]>(`/api/agent/decisions?limit=${limit}`),
  getRecentEvents: (limit = 50) => getJSON<EventTraceSummary[]>(`/api/events/recent?limit=${limit}`),
  getEventTrace: (eventId: string) => getJSON<EventTrace>(`/api/events/${encodeURIComponent(eventId)}/trace`),
};

// Exported for places that might want a typed POST without a dedicated
// helper above (none of this project's endpoints need one yet, but the
// pattern is here for the next endpoint that does).
export { postJSON };

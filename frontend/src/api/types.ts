// These shapes mirror the dataclasses/dicts the FastAPI backend returns.
// Kept in one file and hand-written (rather than generated) since the
// backend is small enough that keeping them in sync by hand isn't a
// burden - if this grew much further, generating these from the FastAPI
// OpenAPI schema would be the next step.

export type Health = "healthy" | "unhealthy";
export type EventKind = "metric" | "log" | "alert";

export interface EntitySummary {
  entity_id: string;
  entity_type: "host" | "service";
  canonical_name: string;
  health: Health;
  last_updated: number;
}

export interface RecentEventSummary {
  event_id: string;
  source: string;
  kind: EventKind;
  fields: Record<string, unknown>;
  received_at: number;
}

export interface DeployRecord {
  entity_id: string;
  deployed_at: number;
  version: string;
}

export interface EntityState extends EntitySummary {
  last_metric: Record<string, number> | null;
  dependency_context: {
    depends_on: string[];
    depended_on_by: string[];
  };
  recent_deploys: DeployRecord[];
  recent_events: RecentEventSummary[];
}

export interface Decision {
  decision_id: string;
  entity_id: string;
  created_at: number;
  action: "rollback" | "investigate_dependency" | "restart";
  rule: string;
  reasoning: string;
  facts: {
    health: Health;
    recent_deploys: DeployRecord[];
    dependency_healths: Record<string, Health>;
  };
}

export interface StageMetrics {
  throughput_per_sec: number;
  latency_ms: { p50: number; p95: number; p99: number };
  processed_total: number;
  error_total: number;
  queue_depth: number;
}

export type PipelineMetrics = Record<string, StageMetrics>;

export interface EventTraceSummary {
  event_id: string;
  source: string | null;
  kind: EventKind | null;
  entity_ref: string | null;
  canonical_id: string | null;
  complete: boolean;
}

export interface EventTrace {
  event_id: string;
  raw?: Record<string, unknown>;
  normalized?: Record<string, unknown>;
  linked?: Record<string, unknown>;
  enriched?: Record<string, unknown>;
}

export type WsMessage =
  | { type: "event"; data: RecentEventSummary & { entity_ref: string; canonical_id: string | null } }
  | { type: "entity_update"; data: EntityState }
  | { type: "decision"; data: Decision }
  | { type: "metrics"; data: PipelineMetrics };

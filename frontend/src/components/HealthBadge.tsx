import type { Health } from "../api/types";

export function HealthBadge({ health }: { health: Health }) {
  const isHealthy = health === "healthy";
  return (
    <span className={`health-badge ${isHealthy ? "health-badge--healthy" : "health-badge--unhealthy"}`}>
      <span className="health-badge__dot" />
      {health}
    </span>
  );
}

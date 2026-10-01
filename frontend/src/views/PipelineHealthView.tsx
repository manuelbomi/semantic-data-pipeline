import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useLiveStore } from "../api/useLiveStore";
import { StatTile } from "../components/StatTile";

const STAGE_ORDER = ["normalize", "entity_link", "enrich", "publish"] as const;
const STAGE_LABELS: Record<string, string> = {
  normalize: "Normalize",
  entity_link: "Entity Link",
  enrich: "Enrich",
  publish: "Publish",
};
// One fixed, distinguishable color per stage, reused in the chart legend
// and the stat tiles below so the mapping is consistent everywhere.
const STAGE_COLORS: Record<string, string> = {
  normalize: "#3b82f6",
  entity_link: "#14b8a6",
  enrich: "#f59e0b",
  publish: "#8b5cf6",
};

export function PipelineHealthView() {
  const { metricsLatest, metricsHistory } = useLiveStore();

  const chartData = metricsHistory.map((sample) => {
    const row: Record<string, number | string> = {
      time: new Date(sample.timestamp).toLocaleTimeString(),
    };
    for (const stage of STAGE_ORDER) {
      row[stage] = sample.metrics[stage]?.throughput_per_sec ?? 0;
    }
    return row;
  });

  return (
    <div className="view">
      <h2 className="view__title">Pipeline Health</h2>
      <p className="view__subtitle">
        Throughput, latency and queue depth per stage, computed from real event timestamps - not sampled, not estimated.
      </p>

      <div className="chart-card">
        <h3 className="chart-card__title">Throughput per stage (events/sec)</h3>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="chart-grid" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} minTickGap={30} />
            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
            <Tooltip />
            <Legend formatter={(value) => STAGE_LABELS[value] ?? value} />
            {STAGE_ORDER.map((stage) => (
              <Line
                key={stage}
                type="monotone"
                dataKey={stage}
                stroke={STAGE_COLORS[stage]}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="stage-grid">
        {STAGE_ORDER.map((stage) => {
          const m = metricsLatest?.[stage];
          return (
            <div className="stage-card" key={stage} style={{ borderTopColor: STAGE_COLORS[stage] }}>
              <h3 className="stage-card__title">{STAGE_LABELS[stage]}</h3>
              <div className="stage-card__stats">
                <StatTile label="Throughput" value={`${m?.throughput_per_sec ?? 0}/s`} />
                <StatTile label="p50 latency" value={`${m?.latency_ms.p50 ?? 0} ms`} />
                <StatTile label="p99 latency" value={`${m?.latency_ms.p99 ?? 0} ms`} />
                <StatTile label="Queue depth" value={m?.queue_depth ?? 0} sublabel="backpressure" />
                <StatTile label="Processed" value={m?.processed_total ?? 0} />
                <StatTile label="Errors" value={m?.error_total ?? 0} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

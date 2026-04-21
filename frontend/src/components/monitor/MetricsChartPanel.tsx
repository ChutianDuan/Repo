import type { MetricPoint } from "../../types/monitor";

interface MetricsChartPanelProps {
  points: MetricPoint[];
}

function MiniChart({ label, values, suffix = "" }: { label: string; values: Array<number | null | undefined>; suffix?: string }) {
  const cleaned = values.map((value) => (value === null || value === undefined ? 0 : value));
  const max = Math.max(1, ...cleaned);

  return (
    <article className="mini-chart">
      <div>
        <h3>{label}</h3>
        <span>{cleaned.length ? `${Math.round(cleaned[cleaned.length - 1])}${suffix}` : "--"}</span>
      </div>
      <div className="mini-chart__bars">
        {cleaned.map((value, index) => (
          <i key={`${label}-${index}`} style={{ height: `${Math.max(8, (value / max) * 100)}%` }} />
        ))}
      </div>
    </article>
  );
}

export function MetricsChartPanel({ points }: MetricsChartPanelProps) {
  return (
    <div className="metrics-chart-panel">
      <MiniChart label="CPU Trend" values={points.map((point) => point.cpu)} suffix="%" />
      <MiniChart label="GPU Trend" values={points.map((point) => point.gpu)} suffix="%" />
      <MiniChart label="API Latency" values={points.map((point) => point.api_ms)} suffix="ms" />
      <MiniChart label="Task Throughput" values={points.map((point) => point.throughput)} />
    </div>
  );
}

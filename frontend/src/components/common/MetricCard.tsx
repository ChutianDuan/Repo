interface MetricCardProps {
  label: string;
  value: string;
  detail?: string;
  tone?: "default" | "ok" | "warn" | "error";
}

export function MetricCard({ label, value, detail, tone = "default" }: MetricCardProps) {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </article>
  );
}

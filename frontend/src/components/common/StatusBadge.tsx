interface StatusBadgeProps {
  label: string;
  tone?: "ok" | "warn" | "error" | "muted";
}

export function StatusBadge({ label, tone = "muted" }: StatusBadgeProps) {
  return <span className={`status-badge status-badge--${tone}`}>{label}</span>;
}

import type { ServiceState } from "../../types/monitor";

interface HealthDotProps {
  label: string;
  state: ServiceState;
  compact?: boolean;
}

export function HealthDot({ label, state, compact = false }: HealthDotProps) {
  return (
    <span className={`health-dot health-dot--${state}`} title={`${label}: ${state}`}>
      <span aria-hidden="true" />
      {compact ? null : label}
    </span>
  );
}

interface ProgressBarProps {
  value: number;
}

export function ProgressBar({ value }: ProgressBarProps) {
  const normalized = Math.max(0, Math.min(100, Math.round(value || 0)));
  return (
    <div className="progress-bar" aria-label={`progress ${normalized}%`}>
      <span style={{ width: `${normalized}%` }} />
    </div>
  );
}

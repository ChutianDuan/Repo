import { formatDateTime } from "../../utils/format";

interface TimestampTextProps {
  value?: string | null;
}

export function TimestampText({ value }: TimestampTextProps) {
  return <time className="timestamp-text">{formatDateTime(value)}</time>;
}

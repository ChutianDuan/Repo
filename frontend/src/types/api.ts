export interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
}

export interface DependencyStatus {
  ok: boolean;
  error?: string;
}

export interface InternalDependencyStatus {
  ok: boolean;
  code?: number | null;
  message?: string | null;
}

export interface HealthSnapshot {
  ok: boolean;
  mysql: DependencyStatus;
  redis: DependencyStatus;
  python: DependencyStatus;
}

export interface InternalHealthSnapshot {
  ok: boolean;
  mysql: InternalDependencyStatus;
  redis: InternalDependencyStatus;
}

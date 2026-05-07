import type { GpuMetrics } from "../types/monitor";

function finiteValues(values: Array<number | null | undefined>): number[] {
  return values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
}

export function summarizeGpuMetrics(gpus: GpuMetrics[]) {
  if (gpus.length === 0) {
    return {
      label: "No GPU telemetry",
      util_percent: null,
      memory_used_mb: null,
      memory_total_mb: null,
    };
  }

  const utilValues = finiteValues(gpus.map((gpu) => gpu.util_percent));
  const memoryUsedValues = finiteValues(gpus.map((gpu) => gpu.memory_used_mb));
  const memoryTotalValues = finiteValues(gpus.map((gpu) => gpu.memory_total_mb));
  const gpuIds = gpus.map((gpu) => gpu.id).join(", ");

  return {
    label: gpus.length === 1 ? gpus[0].name : `GPU ${gpuIds}`,
    util_percent:
      utilValues.length > 0
        ? utilValues.reduce((sum, value) => sum + value, 0) / utilValues.length
        : null,
    memory_used_mb:
      memoryUsedValues.length > 0
        ? memoryUsedValues.reduce((sum, value) => sum + value, 0)
        : null,
    memory_total_mb:
      memoryTotalValues.length > 0
        ? memoryTotalValues.reduce((sum, value) => sum + value, 0)
        : null,
  };
}

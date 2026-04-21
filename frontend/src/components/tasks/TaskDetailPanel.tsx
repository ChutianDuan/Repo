import type { TaskRecord } from "../../types/task";
import { EmptyState } from "../common/EmptyState";
import { ProgressBar } from "../common/ProgressBar";
import { StatusBadge } from "../common/StatusBadge";
import { TimestampText } from "../common/TimestampText";
import { stateTone } from "../../utils/format";

interface TaskDetailPanelProps {
  task: TaskRecord | null;
}

function formatMeta(meta: Record<string, unknown> | null | undefined): string {
  if (!meta) {
    return "{}";
  }
  return JSON.stringify(meta, null, 2);
}

export function TaskDetailPanel({ task }: TaskDetailPanelProps) {
  if (!task) {
    return <EmptyState title="未选择任务" description="从任务表中选择一条记录查看阶段、meta_json 和错误日志。" />;
  }

  return (
    <aside className="task-detail-panel">
      <div className="detail-drawer__head">
        <div>
          <p className="eyebrow">Task Detail</p>
          <h2>{task.type}</h2>
        </div>
        <StatusBadge label={task.state} tone={stateTone(task.state)} />
      </div>

      <div className="detail-grid">
        <span>task_id</span>
        <code>{task.task_id}</code>
        <span>entity</span>
        <strong>
          {task.entity_type}_{task.entity_id}
        </strong>
        <span>created</span>
        <TimestampText value={task.created_at} />
        <span>updated</span>
        <TimestampText value={task.updated_at} />
      </div>

      <section className="drawer-section">
        <h3>Stage Timeline</h3>
        <ProgressBar value={task.progress} />
        <p className="muted">{String(task.meta?.stage || "waiting")}</p>
      </section>

      {task.error ? (
        <section className="task-error-alert">
          <h3>Error Log</h3>
          <p>{task.error}</p>
        </section>
      ) : null}

      <section className="drawer-section">
        <h3>meta_json</h3>
        <pre className="json-viewer">{formatMeta(task.meta)}</pre>
      </section>
    </aside>
  );
}

import type { DocumentListItem } from "../../types/document";
import type { TaskRecord } from "../../types/task";
import { EmptyState } from "../common/EmptyState";
import { ProgressBar } from "../common/ProgressBar";
import { StatusBadge } from "../common/StatusBadge";
import { TimestampText } from "../common/TimestampText";
import { stateTone } from "../../utils/format";

interface DocumentDetailDrawerProps {
  document: DocumentListItem | null;
  tasks: TaskRecord[];
}

function metaValue(task: TaskRecord | undefined, key: string): string {
  const value = task?.meta?.[key];
  return value === undefined || value === null ? "--" : String(value);
}

export function DocumentDetailDrawer({ document, tasks }: DocumentDetailDrawerProps) {
  if (!document) {
    return <EmptyState title="未选择文档" description="从表格中选择一份文档查看 metadata、chunk 和任务记录。" />;
  }

  const ingestTask = tasks.find((task) => task.task_id === document.task_id);

  return (
    <aside className="document-detail-drawer">
      <div className="detail-drawer__head">
        <div>
          <p className="eyebrow">Document Detail</p>
          <h2>{document.filename}</h2>
        </div>
        <StatusBadge label={document.status} tone={stateTone(document.status)} />
      </div>

      <div className="detail-grid">
        <span>doc_id</span>
        <strong>{document.doc_id}</strong>
        <span>created</span>
        <TimestampText value={document.created_at} />
        <span>chunks</span>
        <strong>{document.chunks ?? "--"}</strong>
        <span>vectorized</span>
        <strong>{document.vectorized ? "Yes" : "No"}</strong>
      </div>

      <section className="drawer-section">
        <h3>Index Progress</h3>
        <ProgressBar value={document.progress || 0} />
        <small>{metaValue(ingestTask, "stage")}</small>
      </section>

      <section className="drawer-section">
        <h3>Chunks</h3>
        <p className="muted">{document.chunks ? `${document.chunks} chunks indexed` : "暂无 chunk 信息。"}</p>
      </section>

      <section className="drawer-section">
        <h3>Task History</h3>
        {tasks.length === 0 ? (
          <p className="muted">暂无相关任务。</p>
        ) : (
          <div className="mini-task-list">
            {tasks.map((task) => (
              <article key={task.task_id}>
                <div>
                  <strong>{task.type}</strong>
                  <StatusBadge label={task.state} tone={stateTone(task.state)} />
                </div>
                <ProgressBar value={task.progress} />
                <small>{task.error || metaValue(task, "stage")}</small>
              </article>
            ))}
          </div>
        )}
      </section>
    </aside>
  );
}

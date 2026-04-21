import type { TaskRecord } from "../../types/task";
import { EmptyState } from "../common/EmptyState";
import { ProgressBar } from "../common/ProgressBar";
import { StatusBadge } from "../common/StatusBadge";
import { TimestampText } from "../common/TimestampText";
import { stateTone } from "../../utils/format";

interface TaskTableProps {
  tasks: TaskRecord[];
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
}

export function TaskTable({ tasks, selectedTaskId, onSelectTask }: TaskTableProps) {
  if (tasks.length === 0) {
    return (
      <EmptyState
        title="暂无任务"
        description="上传文档或发起问答后，ingest / chat 任务会进入这里。"
      />
    );
  }

  return (
    <div className="data-table task-table">
      <div className="data-table__row data-table__row--head">
        <span>Task ID</span>
        <span>Type</span>
        <span>State</span>
        <span>Progress</span>
        <span>Entity</span>
        <span>Updated At</span>
      </div>
      {tasks.map((task) => (
        <button
          type="button"
          key={task.task_id}
          className={task.task_id === selectedTaskId ? "data-table__row data-table__row--active" : "data-table__row"}
          onClick={() => onSelectTask(task.task_id)}
        >
          <code>{task.task_id.slice(0, 8)}</code>
          <span>{task.type}</span>
          <StatusBadge label={task.state} tone={stateTone(task.state)} />
          <ProgressBar value={task.progress} />
          <span>
            {task.entity_type}_{task.entity_id}
          </span>
          <TimestampText value={task.updated_at || task.created_at} />
        </button>
      ))}
    </div>
  );
}

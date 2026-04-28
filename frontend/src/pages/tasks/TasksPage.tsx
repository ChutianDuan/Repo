import { useState } from "react";
import type { TaskRecord } from "../../types/task";
import { MetricCard } from "../../components/common/MetricCard";
import { PageTitle } from "../../components/common/PageTitle";
import { SectionCard } from "../../components/common/SectionCard";
import { TaskDetailPanel } from "../../components/tasks/TaskDetailPanel";
import { TaskTable } from "../../components/tasks/TaskTable";
import { formatNumber } from "../../utils/format";

interface TasksPageProps {
  tasks: TaskRecord[];
  selectedTaskId: string | null;
  taskListError: string | null;
  onSelectTask: (taskId: string) => void;
  onRefreshTasks: () => void;
}

type TaskFilter = "all" | "ingest" | "chat" | "failed" | "running";

export function TasksPage({ tasks, selectedTaskId, taskListError, onSelectTask, onRefreshTasks }: TasksPageProps) {
  const [filter, setFilter] = useState<TaskFilter>("all");
  const filteredTasks = tasks.filter((task) => {
    if (filter === "all") {
      return true;
    }
    if (filter === "ingest") {
      return task.type.includes("ingest");
    }
    if (filter === "chat") {
      return task.type.includes("chat");
    }
    if (filter === "failed") {
      return task.state === "FAILURE" || task.state === "FAILED";
    }
    return !["SUCCESS", "FAILURE", "FAILED"].includes(task.state);
  });
  const selectedTask = tasks.find((task) => task.task_id === selectedTaskId) || null;
  const runningCount = tasks.filter((task) => !["SUCCESS", "FAILURE", "FAILED"].includes(task.state)).length;
  const failedCount = tasks.filter((task) => task.state === "FAILURE" || task.state === "FAILED").length;
  const successCount = tasks.filter((task) => task.state === "SUCCESS").length;

  return (
    <div className="tasks-page page-stack">
      <PageTitle
        eyebrow="Pipeline"
        title="Tasks"
        description="观察 ingest、embedding、indexing、chat 任务的状态、进度和错误原因。"
        action={
          <button type="button" onClick={onRefreshTasks}>
            Refresh
          </button>
        }
      />

      {taskListError ? <div className="notice-box">{taskListError}</div> : null}

      <div className="summary-grid">
        <MetricCard label="Total Tasks" value={formatNumber(tasks.length)} />
        <MetricCard label="Running" value={formatNumber(runningCount)} tone="warn" />
        <MetricCard label="Success" value={formatNumber(successCount)} tone="ok" />
        <MetricCard label="Failed" value={formatNumber(failedCount)} tone={failedCount > 0 ? "error" : "default"} />
      </div>

      <SectionCard
        title="Task Table"
        description="按类型和状态筛选任务。"
        action={
          <div className="filter-tabs">
            {(["all", "ingest", "chat", "running", "failed"] as TaskFilter[]).map((item) => (
              <button
                key={item}
                type="button"
                className={filter === item ? "filter-tab filter-tab--active" : "filter-tab"}
                onClick={() => setFilter(item)}
              >
                {item}
              </button>
            ))}
          </div>
        }
      >
        <div className="split-panel">
          <TaskTable tasks={filteredTasks} selectedTaskId={selectedTaskId} onSelectTask={onSelectTask} />
          <TaskDetailPanel task={selectedTask} />
        </div>
      </SectionCard>
    </div>
  );
}

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
      return task.type.includes("ingest") || task.type === "parse_document" || task.type === "build_embedding";
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
        eyebrow="处理进度"
        title="任务"
        description="查看文档索引和问答任务是否完成。"
        action={
          <button type="button" onClick={onRefreshTasks}>
            刷新
          </button>
        }
      />

      {taskListError ? <div className="notice-box">{taskListError}</div> : null}

      <div className="summary-grid">
        <MetricCard label="任务总数" value={formatNumber(tasks.length)} />
        <MetricCard label="运行中" value={formatNumber(runningCount)} tone="warn" />
        <MetricCard label="成功" value={formatNumber(successCount)} tone="ok" />
        <MetricCard label="失败" value={formatNumber(failedCount)} tone={failedCount > 0 ? "error" : "default"} />
      </div>

      <SectionCard
        title="任务列表"
        description="按类型或状态查看处理结果。"
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

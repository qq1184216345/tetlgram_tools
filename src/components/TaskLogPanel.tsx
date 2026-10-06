import { TaskInfo } from "../api/client";

interface TaskLogPanelProps {
  task: TaskInfo | null;
  onRetryFailed?: (targets: string[]) => void;
}

const LEVEL_CLASS: Record<string, string> = {
  info: "log-info",
  success: "log-success",
  warn: "log-warn",
  error: "log-error",
};

export function TaskLogPanel({ task, onRetryFailed }: TaskLogPanelProps) {
  if (!task) {
    return (
      <div className="card task-log-panel">
        <h3>任务日志</h3>
        <p className="muted">启动任务后在此查看实时日志</p>
      </div>
    );
  }

  const { progress } = task;
  const failedItems = task.failed_items ?? [];
  const canRetry =
    Boolean(onRetryFailed) &&
    failedItems.length > 0 &&
    !["running", "paused", "stopping", "pending"].includes(task.status);

  return (
    <div className="card task-log-panel">
      <div className="card-header">
        <h3>任务日志</h3>
        <span className={`badge badge-${task.status}`}>{task.status}</span>
      </div>
      <div className="task-progress">
        进度: {progress.current}/{progress.total} | 成功: {progress.success} | 失败:{" "}
        {progress.failed}
      </div>
      {task.result_file && (
        <div className="task-result">结果文件: {task.result_file}</div>
      )}

      {failedItems.length > 0 && (
        <div className="failed-items">
          <div className="failed-items-header">
            <strong>失败明细（{failedItems.length}）</strong>
            {canRetry && (
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  onRetryFailed?.(failedItems.map((item) => item.target).filter(Boolean))
                }
              >
                重试失败目标
              </button>
            )}
          </div>
          <div className="failed-items-list">
            {failedItems.map((item, index) => (
              <div key={`${item.target}-${index}`} className="failed-item">
                <span className="failed-target">{item.target}</span>
                <span className="failed-reason">{item.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="log-list">
        {task.logs.length === 0 ? (
          <p className="muted">等待日志...</p>
        ) : (
          task.logs.map((entry, index) => (
            <div
              key={`${entry.time}-${index}`}
              className={`log-entry ${LEVEL_CLASS[entry.level] ?? "log-info"}`}
            >
              <span className="log-time">{entry.time}</span>
              <span>{entry.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

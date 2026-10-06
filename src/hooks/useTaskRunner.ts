import { useCallback, useMemo, useState } from "react";
import { api, TaskInfo } from "../api/client";
import { TASK_TYPE_LABEL, useGlobalTask } from "../context/TaskContext";
import { useToast } from "../context/ToastContext";

function confirmParallelTask(
  runningTasks: TaskInfo[],
  nextAccountIds: string[],
): boolean {
  const primary = runningTasks[0];
  if (!primary) return true;

  const busy = [...new Set(runningTasks.flatMap((t) => t.account_ids ?? []))];
  const overlap = nextAccountIds.filter((id) => busy.includes(id));
  const typeLabel = TASK_TYPE_LABEL[primary.type] || primary.type;
  const lines = [
    `当前已有 ${runningTasks.length} 个任务在执行（例如: ${typeLabel}）。`,
    "底部日志已按任务分 Tab，可切换查看。",
    "",
  ];
  if (overlap.length) {
    lines.push(`冲突账号: ${overlap.join(", ")}`);
    lines.push("同一账号并行可能导致连接冲突，并加重频繁限制。");
  } else if (busy.length) {
    lines.push(`占用中账号: ${busy.join(", ")}`);
    lines.push("账号不同时一般可并行，仍请注意接口频率。");
  } else {
    lines.push("请确认不会误选相同账号。");
  }
  lines.push("", "确定仍要创建新任务吗？");
  return window.confirm(lines.join("\n"));
}

interface RunOptions {
  requireAccounts?: boolean;
}

export function useTaskRunner(...taskTypes: string[]) {
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const toast = useToast();
  const { setGlobalTask, isTaskRunning, runningTasks, tasks } = useGlobalTask();
  const typeKey = taskTypes.join("\0");
  const typeList = useMemo(
    () => typeKey.split("\0").filter(Boolean),
    [typeKey],
  );

  const currentTask = useMemo(() => {
    if (currentTaskId) {
      const pinned = tasks.find((task) => task.id === currentTaskId);
      if (pinned) return pinned;
    }
    if (!typeList.length) return null;
    const match = (task: TaskInfo) => typeList.includes(task.type);
    return runningTasks.find(match) ?? tasks.find(match) ?? null;
  }, [currentTaskId, tasks, runningTasks, typeList]);

  const isRunning =
    currentTask?.status === "running" ||
    currentTask?.status === "stopping" ||
    currentTask?.status === "paused";

  const isPaused = currentTask?.status === "paused";

  async function run(
    fn: () => Promise<TaskInfo>,
    accountIds: string[] = [],
    options: RunOptions = {},
  ) {
    if (options.requireAccounts && accountIds.length === 0) {
      toast.error("请先勾选在线账号");
      return;
    }

    const others = runningTasks.filter(
      (task) => !(isPaused && currentTask && task.id === currentTask.id),
    );
    if (isTaskRunning && others.length > 0) {
      if (!confirmParallelTask(others, accountIds)) {
        toast.info("已取消创建新任务");
        return;
      }
    }

    setLoading(true);
    try {
      const task = await fn();
      setCurrentTaskId(task.id);
      setGlobalTask(task);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  const control = useCallback(
    async (action: "stop" | "pause" | "resume") => {
      if (!currentTask) return;
      setLoading(true);
      try {
        const updated =
          action === "stop"
            ? await api.stopTask(currentTask.id)
            : action === "pause"
              ? await api.pauseTask(currentTask.id)
              : await api.resumeTask(currentTask.id);
        setCurrentTaskId(updated.id);
        setGlobalTask(updated);
      } catch (err) {
        const fallback =
          action === "stop" ? "停止失败" : action === "pause" ? "暂停失败" : "恢复失败";
        toast.error(err instanceof Error ? err.message : fallback);
      } finally {
        setLoading(false);
      }
    },
    [currentTask, setGlobalTask, toast],
  );

  return {
    currentTask,
    loading,
    isRunning,
    isPaused,
    run,
    stop: () => control("stop"),
    pause: () => control("pause"),
    resume: () => control("resume"),
  };
}

export function parseLines(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

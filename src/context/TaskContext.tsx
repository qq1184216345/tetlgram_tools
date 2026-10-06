import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  ReactNode,
} from "react";
import { api, TaskInfo } from "../api/client";

const ACTIVE_STATUSES = new Set(["running", "paused", "stopping", "pending"]);

interface TaskContextValue {
  /** 当前底部日志选中的任务 */
  globalTask: TaskInfo | null;
  /** 写入/更新任务，并切换为当前选中 */
  setGlobalTask: (task: TaskInfo | null) => void;
  tasks: TaskInfo[];
  activeTaskId: string | null;
  setActiveTaskId: (id: string | null) => void;
  upsertTask: (task: TaskInfo) => void;
  isTaskRunning: boolean;
  runningTasks: TaskInfo[];
}

const TaskContext = createContext<TaskContextValue | null>(null);

function sortTasks(list: TaskInfo[]): TaskInfo[] {
  return [...list].sort((a, b) => {
    const aActive = ACTIVE_STATUSES.has(a.status) ? 1 : 0;
    const bActive = ACTIVE_STATUSES.has(b.status) ? 1 : 0;
    if (aActive !== bActive) return bActive - aActive;
    return (b.created_at || "").localeCompare(a.created_at || "");
  });
}

export function TaskProvider({ children }: { children: ReactNode }) {
  const [tasksById, setTasksById] = useState<Record<string, TaskInfo>>({});
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);

  const upsertTask = useCallback((task: TaskInfo) => {
    setTasksById((prev) => ({ ...prev, [task.id]: task }));
  }, []);

  const setGlobalTask = useCallback((task: TaskInfo | null) => {
    if (!task) return;
    setTasksById((prev) => ({ ...prev, [task.id]: task }));
    setActiveTaskId(task.id);
  }, []);

  const hasActive = useMemo(
    () => Object.values(tasksById).some((task) => ACTIVE_STATUSES.has(task.status)),
    [tasksById],
  );

  useEffect(() => {
    let cancelled = false;
    const sync = async () => {
      try {
        const list = await api.listTasks();
        if (cancelled) return;
        setTasksById((prev) => {
          const next = { ...prev };
          for (const task of list) {
            next[task.id] = task;
          }
          return next;
        });
      } catch {
        /* ignore */
      }
    };
    void sync();
    const timer = setInterval(() => void sync(), hasActive ? 1200 : 4000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [hasActive]);

  const tasks = useMemo(() => sortTasks(Object.values(tasksById)), [tasksById]);
  const runningTasks = useMemo(
    () => tasks.filter((t) => ACTIVE_STATUSES.has(t.status)),
    [tasks],
  );
  const isTaskRunning = runningTasks.some(
    (t) => t.status === "running" || t.status === "paused",
  );

  const globalTask = useMemo(() => {
    if (activeTaskId && tasksById[activeTaskId]) {
      return tasksById[activeTaskId];
    }
    return runningTasks[0] ?? tasks[0] ?? null;
  }, [activeTaskId, tasksById, runningTasks, tasks]);

  const value = useMemo(
    () => ({
      globalTask,
      setGlobalTask,
      tasks,
      activeTaskId: globalTask?.id ?? null,
      setActiveTaskId,
      upsertTask,
      isTaskRunning,
      runningTasks,
    }),
    [
      globalTask,
      setGlobalTask,
      tasks,
      setActiveTaskId,
      upsertTask,
      isTaskRunning,
      runningTasks,
    ],
  );

  return <TaskContext.Provider value={value}>{children}</TaskContext.Provider>;
}

export function useGlobalTask() {
  const ctx = useContext(TaskContext);
  if (!ctx) {
    throw new Error("useGlobalTask must be used within TaskProvider");
  }
  return ctx;
}

export const TASK_TYPE_LABEL: Record<string, string> = {
  connect_accounts: "连号",
  broadcast: "群发",
  join_group: "加群",
  dm: "私信",
  scrape_members: "采集成员",
  scrape_groups: "搜群",
  invite: "拉人",
  warm_group: "炒群",
  monitor: "监控",
  filter_groups: "筛群",
  update_profile: "改资料",
  extract_links: "提取链接",
  leave_groups: "退群",
  channel_comment: "评论频道",
  clone_channel: "克隆频道",
  scrape_profiles: "用户资料",
};

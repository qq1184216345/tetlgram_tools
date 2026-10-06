import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { api, TaskInfo } from "../api/client";
import { TASK_TYPE_LABEL, useGlobalTask } from "../context/TaskContext";
import { useToast } from "../context/ToastContext";
import { LOG_COLLAPSE_KEY, taskStatusLabel } from "../lib/labels";

const LEVEL_CLASS: Record<string, string> = {
  info: "log-info",
  success: "log-success",
  warn: "log-warn",
  error: "log-error",
};

const COLLAPSE_KEY = LOG_COLLAPSE_KEY;
const HEIGHT_KEY = "telegram_tools_log_height";
const DEFAULT_HEIGHT = 280;
const MIN_HEIGHT = 140;
const MAX_HEIGHT_RATIO = 0.72;

function loadCollapsed(): boolean {
  try {
    const raw = localStorage.getItem(COLLAPSE_KEY);
    if (raw === null) return true;
    return raw === "1";
  } catch {
    return true;
  }
}

function loadHeight(): number {
  try {
    const raw = Number(localStorage.getItem(HEIGHT_KEY));
    if (Number.isFinite(raw) && raw >= MIN_HEIGHT) {
      return Math.round(raw);
    }
  } catch {
    /* ignore */
  }
  return DEFAULT_HEIGHT;
}

function clampHeight(value: number): number {
  const maxH = Math.floor(window.innerHeight * MAX_HEIGHT_RATIO);
  return Math.min(maxH, Math.max(MIN_HEIGHT, Math.round(value)));
}

function taskTabLabel(task: TaskInfo): string {
  const type = TASK_TYPE_LABEL[task.type] || task.type;
  const shortId = task.id.slice(0, 4);
  return `${type}·${shortId}`;
}

function filterLogsByAccount(task: TaskInfo, accountFilter: string) {
  if (!accountFilter || accountFilter === "all") {
    return task.logs;
  }
  const token = `[${accountFilter}]`;
  return task.logs.filter((entry) => entry.message.includes(token));
}

export function GlobalLogPanel() {
  const {
    globalTask,
    tasks,
    setActiveTaskId,
    upsertTask,
    runningTasks,
  } = useGlobalTask();
  const toast = useToast();
  const logRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);
  const [lastExportPath, setLastExportPath] = useState("");
  const [collapsed, setCollapsed] = useState(loadCollapsed);
  const [accountFilter, setAccountFilter] = useState("all");
  const [height, setHeight] = useState(loadHeight);
  const [dragging, setDragging] = useState(false);
  const heightRef = useRef(height);
  const dragStartY = useRef(0);
  const dragStartH = useRef(DEFAULT_HEIGHT);

  heightRef.current = height;
  const prevRunning = useRef(0);

  useEffect(() => {
    const next = runningTasks.length;
    if (prevRunning.current === 0 && next > 0) {
      setCollapsed(false);
      try {
        localStorage.setItem(COLLAPSE_KEY, "0");
      } catch {
        /* ignore */
      }
    }
    prevRunning.current = next;
  }, [runningTasks.length]);

  // 切换任务时重置账号筛选
  useEffect(() => {
    setAccountFilter("all");
  }, [globalTask?.id]);

  useEffect(() => {
    if (!collapsed && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [globalTask?.logs.length, accountFilter, collapsed, globalTask?.id]);

  useEffect(() => {
    if (!dragging) return;

    const onMove = (e: MouseEvent) => {
      const delta = dragStartY.current - e.clientY;
      setHeight(clampHeight(dragStartH.current + delta));
    };

    const onUp = () => {
      setDragging(false);
      try {
        localStorage.setItem(HEIGHT_KEY, String(heightRef.current));
      } catch {
        /* ignore */
      }
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "ns-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [dragging]);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  function startResize(e: ReactMouseEvent) {
    if (collapsed || e.button !== 0) return;
    e.preventDefault();
    dragStartY.current = e.clientY;
    dragStartH.current = heightRef.current;
    setDragging(true);
  }

  function resetHeight() {
    const next = clampHeight(DEFAULT_HEIGHT);
    setHeight(next);
    try {
      localStorage.setItem(HEIGHT_KEY, String(next));
    } catch {
      /* ignore */
    }
  }

  async function handleExport() {
    if (!globalTask) return;
    setExporting(true);
    try {
      const result = await api.exportTaskLog(globalTask.id);
      const path = String(result.data?.path || "");
      setLastExportPath(path);
      toast.success(result.message || (path ? `已保存到 ${path}` : "导出成功"));
      const refreshed = await api.getTask(globalTask.id);
      upsertTask(refreshed);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "导出失败");
    } finally {
      setExporting(false);
    }
  }

  const task = globalTask;
  const accountIds = useMemo(() => {
    const fromTask = task?.account_ids ?? [];
    if (fromTask.length) return fromTask;
    // 兜底：从日志里解析 [account]
    const found = new Set<string>();
    for (const entry of task?.logs ?? []) {
      const m = entry.message.match(/\[(\d{6,}|[A-Za-z0-9_+.-]{4,})\]/);
      if (m) found.add(m[1]);
    }
    return [...found];
  }, [task]);

  const visibleLogs = useMemo(
    () => (task ? filterLogsByAccount(task, accountFilter) : []),
    [task, accountFilter],
  );

  const recentTasks = useMemo(() => tasks.slice(0, 12), [tasks]);

  return (
    <div
      className={`global-log-panel${collapsed ? " collapsed" : ""}${dragging ? " dragging" : ""}`}
      style={collapsed ? undefined : { height }}
    >
      {!collapsed && (
        <div
          className="global-log-resize"
          onMouseDown={startResize}
          onDoubleClick={resetHeight}
          title="拖动调整日志高度 · 双击恢复默认"
          role="separator"
          aria-orientation="horizontal"
          aria-label="调整日志区域高度"
        />
      )}
      <div className="global-log-header">
        <button
          type="button"
          className="global-log-toggle"
          onClick={toggleCollapsed}
          title={collapsed ? "展开运行日志" : "收起运行日志"}
        >
          <span className="global-log-chevron" aria-hidden>
            {collapsed ? "▲" : "▼"}
          </span>
          <span>运行日志</span>
          {collapsed && task && (
            <span className="muted global-log-summary">
              {TASK_TYPE_LABEL[task.type] || task.type} · {taskStatusLabel(task.status)} ·{" "}
              {task.progress.current}/{task.progress.total}
            </span>
          )}
        </button>
        <div className="global-log-actions">
          {!collapsed && task && (
            <>
              <span className={`badge badge-${task.status}`}>{taskStatusLabel(task.status)}</span>
              <span className="muted">
                {task.progress.current}/{task.progress.total} | 成功 {task.progress.success} | 失败{" "}
                {task.progress.failed}
              </span>
              <button
                className="secondary"
                onClick={handleExport}
                disabled={!task.logs.length || exporting}
              >
                {exporting ? "导出中..." : "导出日志"}
              </button>
            </>
          )}
          <button type="button" className="secondary" onClick={toggleCollapsed}>
            {collapsed ? "展开" : "收起"}
          </button>
        </div>
      </div>
      {!collapsed && task && task.progress.total > 0 && (
        <div className="task-meter" title={`${task.progress.current}/${task.progress.total}`}>
          <div
            className="task-meter-bar"
            style={{
              width: `${Math.min(
                100,
                Math.round((task.progress.current / Math.max(1, task.progress.total)) * 100),
              )}%`,
            }}
          />
        </div>
      )}

      {!collapsed && recentTasks.length > 0 && (
        <div className="global-log-tabs" role="tablist" aria-label="任务日志">
          {recentTasks.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              className={`global-log-tab${task?.id === item.id ? " active" : ""}`}
              aria-selected={task?.id === item.id}
              onClick={() => setActiveTaskId(item.id)}
              title={`${TASK_TYPE_LABEL[item.type] || item.type} ${item.id}`}
            >
              <span>{taskTabLabel(item)}</span>
              <span className={`tab-dot status-${item.status}`} />
            </button>
          ))}
        </div>
      )}

      {!collapsed && task && accountIds.length > 0 && (
        <div className="global-log-tabs account-tabs" role="tablist" aria-label="按账号筛选">
          <button
            type="button"
            role="tab"
            className={`global-log-tab${accountFilter === "all" ? " active" : ""}`}
            onClick={() => setAccountFilter("all")}
          >
            全部账号
          </button>
          {accountIds.map((id) => (
            <button
              key={id}
              type="button"
              role="tab"
              className={`global-log-tab${accountFilter === id ? " active" : ""}`}
              onClick={() => setAccountFilter(id)}
              title={id}
            >
              {id.length > 12 ? `${id.slice(0, 6)}…${id.slice(-4)}` : id}
            </button>
          ))}
        </div>
      )}

      {!collapsed && lastExportPath && (
        <div className="export-path muted">最近导出: {lastExportPath}</div>
      )}

      {!collapsed && (
        <div className="global-log-body" ref={logRef}>
          {!task || task.logs.length === 0 ? (
            <p className="muted">
              点开始后日志会出现在这里。任务运行时会自动展开。
            </p>
          ) : visibleLogs.length === 0 ? (
            <p className="muted">当前账号筛选下暂无日志</p>
          ) : (
            visibleLogs.map((entry, index) => (
              <div
                key={`${entry.time}-${index}-${entry.message.slice(0, 24)}`}
                className={`log-entry ${LEVEL_CLASS[entry.level] ?? "log-info"}`}
              >
                <span className="log-time">{entry.time}</span>
                <span>{entry.message}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

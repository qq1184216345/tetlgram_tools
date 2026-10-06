export const TASK_STATUS_LABEL: Record<string, string> = {
  pending: "排队中",
  running: "运行中",
  paused: "已暂停",
  stopping: "停止中",
  stopped: "已停止",
  completed: "已完成",
  error: "出错",
};

export function taskStatusLabel(status: string | undefined): string {
  if (!status) return "";
  return TASK_STATUS_LABEL[status] || status;
}

export const PAGE_STORAGE_KEY = "paperwing_active_page";
export const ACCOUNTS_STORAGE_KEY = "paperwing_selected_accounts";
export const LOG_COLLAPSE_KEY = "telegram_tools_log_collapsed";

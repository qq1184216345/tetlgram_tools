import { NavItem, PageId } from "../types";
import { TASK_TYPE_LABEL, useGlobalTask } from "../context/TaskContext";
import { taskStatusLabel } from "../lib/labels";
import logo from "../assets/logo.png";
import { useMemo } from "react";

interface TopNavProps {
  items: NavItem[];
  active: string;
  onSelect: (id: string) => void;
}

const TASK_PAGE: Record<string, PageId> = {
  connect_accounts: "accounts",
  update_profile: "accounts",
  broadcast: "broadcast",
  join_group: "broadcast",
  leave_groups: "broadcast",
  dm: "dm",
  invite: "invite",
  scrape_members: "scrape",
  scrape_groups: "scrape",
  scrape_profiles: "extract",
  extract_links: "extract",
  channel_comment: "extract",
  clone_channel: "extract",
  warm_group: "warm",
  monitor: "monitor",
  filter_groups: "filter",
};

export function TopNav({ items, active, onSelect }: TopNavProps) {
  const { runningTasks } = useGlobalTask();

  const runningPages = useMemo(() => {
    const pages = new Set<string>();
    for (const task of runningTasks) {
      const page = TASK_PAGE[task.type];
      if (page) pages.add(page);
    }
    return pages;
  }, [runningTasks]);

  const settings = items.find((item) => item.id === "settings");
  const tabs = items.filter((item) => item.id !== "settings");
  const runningHint = runningTasks[0];

  return (
    <header className="top-nav">
      <div className="top-nav-brand">
        <img src={logo} alt="纸翼" className="brand-icon" />
        <div>
          <h1>纸翼</h1>
          <p>TG 营销助手</p>
        </div>
      </div>
      <nav className="top-nav-tabs">
        {tabs.map((item) => {
          const running = runningPages.has(item.id);
          return (
            <button
              key={item.id}
              className={`top-tab ${active === item.id ? "active" : ""}`}
              onClick={() => onSelect(item.id)}
              title={item.description}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
              {running && <span className="nav-live-dot" title="有任务正在运行" />}
            </button>
          );
        })}
      </nav>
      {runningHint && (
        <span className="top-nav-running">
          {TASK_TYPE_LABEL[runningHint.type] || runningHint.type} · {taskStatusLabel(runningHint.status)}
          {runningTasks.length > 1 ? ` +${runningTasks.length - 1}` : ""}
        </span>
      )}
      {settings && (
        <button
          className={`top-tab top-tab-settings ${active === "settings" ? "active" : ""}`}
          onClick={() => onSelect("settings")}
          title={settings.description}
        >
          <span className="nav-icon">{settings.icon}</span>
          <span>{settings.label}</span>
        </button>
      )}
    </header>
  );
}

import { ReactNode } from "react";
import { TopNav } from "./TopNav";
import { StatusBar } from "./StatusBar";
import { GlobalLogPanel } from "./GlobalLogPanel";
import { NAV_ITEMS, PageId } from "../types";
import { useLicense } from "../context/LicenseContext";
import { useGlobalTask } from "../context/TaskContext";
import { formatExpiresAt } from "../pages/LicenseGate";
import { usePageHeroAction } from "../context/PageHeroContext";

interface LayoutProps {
  activePage: PageId;
  onPageChange: (page: PageId) => void;
  backendOnline: boolean;
  accountCount: number;
  version: string;
  children: ReactNode;
}

export function Layout({
  activePage,
  onPageChange,
  backendOnline,
  accountCount,
  version,
  children,
}: LayoutProps) {
  const { user } = useLicense();
  const { runningTasks } = useGlobalTask();
  const expiresLabel = formatExpiresAt(user?.expires_at);
  const navItem = NAV_ITEMS.find((item) => item.id === activePage);
  const pageAction = usePageHeroAction(activePage);

  return (
    <div className="app-shell-v2">
      <TopNav
        items={NAV_ITEMS}
        active={activePage}
        onSelect={(id) => onPageChange(id as PageId)}
      />
      <div className="main-panel-v2">
        {navItem && (
          <header className="page-hero">
            <div>
              <h2>{navItem.label}</h2>
              <p>{navItem.description}</p>
            </div>
            <div className="page-hero-right">
              {pageAction}
              {runningTasks.length > 0 && (
                <span className="live-pill">{runningTasks.length} 个任务运行中</span>
              )}
            </div>
          </header>
        )}
        <section className="page-content-v2">{children}</section>
        <GlobalLogPanel />
        <StatusBar
          backendOnline={backendOnline}
          accountCount={accountCount}
          version={version}
          expiresAtLabel={expiresLabel}
        />
      </div>
    </div>
  );
}

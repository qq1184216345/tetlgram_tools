import { useEffect, useState, type ReactElement } from "react";
import { Layout } from "./components/Layout";
import { LicenseProvider, useLicense } from "./context/LicenseContext";
import { PageNavProvider } from "./context/PageNavContext";
import { PageHeroProvider } from "./context/PageHeroContext";
import { TaskProvider } from "./context/TaskContext";
import { ToastProvider } from "./context/ToastContext";
import { PAGE_STORAGE_KEY } from "./lib/labels";
import { AccountsPage } from "./pages/Accounts";
import { BroadcastPage } from "./pages/Broadcast";
import { ScrapePage } from "./pages/Scrape";
import { DirectMessagePage } from "./pages/DirectMessage";
import { InvitePage } from "./pages/Invite";
import { WarmGroupPage } from "./pages/WarmGroup";
import { MonitorPage } from "./pages/Monitor";
import { ExtractPage } from "./pages/Extract";
import { FilterPage } from "./pages/Filter";
import { SettingsPage } from "./pages/Settings";
import { LicenseGate } from "./pages/LicenseGate";
import { UpdateBanner } from "./components/UpdateBanner";
import { api } from "./api/client";
import { BACKEND_PORT } from "./config/ports";
import { NAV_ITEMS, PageId } from "./types";
import "./App.css";

function loadPage(): PageId {
  try {
    const saved = localStorage.getItem(PAGE_STORAGE_KEY);
    if (saved && NAV_ITEMS.some((item) => item.id === saved)) {
      return saved as PageId;
    }
  } catch {
    /* ignore */
  }
  return "accounts";
}

const PAGE_VIEWS: Record<PageId, () => ReactElement> = {
  accounts: () => <AccountsPage />,
  broadcast: () => <BroadcastPage />,
  scrape: () => <ScrapePage />,
  dm: () => <DirectMessagePage />,
  invite: () => <InvitePage />,
  warm: () => <WarmGroupPage />,
  monitor: () => <MonitorPage />,
  extract: () => <ExtractPage />,
  filter: () => <FilterPage />,
  settings: () => <SettingsPage />,
};

function AppShell() {
  const { phase } = useLicense();
  const [activePage, setActivePage] = useState<PageId>(loadPage);
  const [visitedPages, setVisitedPages] = useState<PageId[]>(() => [loadPage()]);

  function handlePageChange(page: PageId) {
    setActivePage(page);
    setVisitedPages((prev) => (prev.includes(page) ? prev : [...prev, page]));
    try {
      localStorage.setItem(PAGE_STORAGE_KEY, page);
    } catch {
      /* ignore */
    }
  }
  const [backendOnline, setBackendOnline] = useState(false);
  const [accountCount, setAccountCount] = useState(0);
  const [version, setVersion] = useState("0.1.0");

  useEffect(() => {
    let cancelled = false;
    let slowTimer: ReturnType<typeof setInterval> | undefined;

    const checkHealth = async () => {
      try {
        const health = await api.health();
        if (cancelled) return;
        setBackendOnline(health.status === "ok");
        setAccountCount(health.accounts);
        setVersion(health.version);
      } catch {
        if (!cancelled) setBackendOnline(false);
      }
    };

    void checkHealth();
    const fastTimer = setInterval(() => {
      void checkHealth();
    }, 2500);
    const switchTimer = setTimeout(() => {
      clearInterval(fastTimer);
      slowTimer = setInterval(() => {
        void checkHealth();
      }, 8000);
    }, 20000);

    return () => {
      cancelled = true;
      clearInterval(fastTimer);
      clearTimeout(switchTimer);
      if (slowTimer) clearInterval(slowTimer);
    };
  }, []);

  if (phase !== "ready") {
    return <LicenseGate />;
  }

  return (
    <PageNavProvider value={handlePageChange}>
    <Layout
      activePage={activePage}
      onPageChange={handlePageChange}
      backendOnline={backendOnline}
      accountCount={accountCount}
      version={version}
    >
      {!backendOnline && activePage !== "settings" && (
        <div className="alert-banner">
          本地后端未就绪（端口 {BACKEND_PORT}）。安装版会自动静默启动，请稍等数秒；若一直失败，可查看应用数据目录中的 backend-startup.log，或重启应用。
        </div>
      )}
      <UpdateBanner localVersion={version} />
      {(Object.keys(PAGE_VIEWS) as PageId[]).map((id) =>
        visitedPages.includes(id) ? (
          <div key={id} className="page-keep-alive" hidden={activePage !== id}>
            {PAGE_VIEWS[id]()}
          </div>
        ) : null,
      )}
    </Layout>
    </PageNavProvider>
  );
}

function App() {
  return (
    <ToastProvider>
      <LicenseProvider>
        <TaskProvider>
          <PageHeroProvider>
            <AppShell />
          </PageHeroProvider>
        </TaskProvider>
      </LicenseProvider>
    </ToastProvider>
  );
}

export default App;

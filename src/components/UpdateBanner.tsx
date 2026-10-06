import { useEffect, useState } from "react";
import { checkForAppUpdate } from "../lib/checkUpdate";

const DISMISS_KEY = "paperwing_update_dismissed";

type BannerState = {
  remote: string;
  local: string;
  notes: string;
  url: string;
  force: boolean;
};

function wasDismissed(remote: string): boolean {
  try {
    return localStorage.getItem(DISMISS_KEY) === remote;
  } catch {
    return false;
  }
}

function dismiss(remote: string): void {
  try {
    localStorage.setItem(DISMISS_KEY, remote);
  } catch {
    /* ignore */
  }
}

export function UpdateBanner({ localVersion }: { localVersion: string }) {
  const [banner, setBanner] = useState<BannerState | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await checkForAppUpdate(localVersion);
      if (cancelled || result.status !== "available") return;
      if (!result.force && wasDismissed(result.remote)) return;
      setBanner({
        remote: result.remote,
        local: result.local,
        notes: result.notes,
        url: result.url,
        force: result.force,
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [localVersion]);

  if (!banner) return null;

  if (banner.force) {
    return (
      <div className="update-force-overlay" role="alertdialog" aria-modal="true">
        <div className="update-force-dialog">
          <h3>必须更新到 {banner.remote}</h3>
          <p className="muted">当前版本 {banner.local} 已停用，请下载安装新版本后继续使用。</p>
          {banner.notes && <p className="update-notes">{banner.notes}</p>}
          {banner.url ? (
            <button
              type="button"
              className="license-primary"
              onClick={() => window.open(banner.url, "_blank", "noopener,noreferrer")}
            >
              打开下载地址
            </button>
          ) : (
            <p className="error">管理员尚未配置下载地址，请联系客服获取安装包。</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="update-banner" role="status">
      <div className="update-banner-body">
        <strong>发现新版本 {banner.remote}</strong>
        <span className="muted">当前 {banner.local}</span>
        {banner.notes && <p>{banner.notes}</p>}
      </div>
      <div className="update-banner-actions">
        {banner.url && (
          <button
            type="button"
            onClick={() => window.open(banner.url, "_blank", "noopener,noreferrer")}
          >
            前往下载
          </button>
        )}
        <button
          type="button"
          className="ghost"
          onClick={() => {
            dismiss(banner.remote);
            setBanner(null);
          }}
        >
          稍后
        </button>
      </div>
    </div>
  );
}

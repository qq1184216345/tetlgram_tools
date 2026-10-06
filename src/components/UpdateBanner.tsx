import { useEffect, useState } from "react";
import { checkForAppUpdate } from "../lib/checkUpdate";
import { startAppUpdate } from "../lib/installUpdate";

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
  const [installing, setInstalling] = useState(false);
  const [error, setError] = useState("");

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

  async function handleInstall() {
    if (!banner?.url || installing) return;
    setInstalling(true);
    setError("");
    try {
      await startAppUpdate(banner.url);
    } catch (err) {
      setInstalling(false);
      setError(err instanceof Error ? err.message : "更新失败");
    }
  }

  return (
    <div className="update-force-overlay" role="alertdialog" aria-modal="true">
      <div className="update-force-dialog">
        <h3>{banner.force ? `必须更新到 ${banner.remote}` : `发现新版本 ${banner.remote}`}</h3>
        <p className="muted">当前版本 {banner.local}</p>
        {banner.notes && <p className="update-notes">{banner.notes}</p>}
        <p className="muted">
          {banner.force
            ? "点击下方按钮会下载安装包并打开安装程序，当前窗口将关闭。"
            : "点击立即更新会下载安装包并打开安装程序，当前窗口将关闭。"}
        </p>
        {error && <p className="error">{error}</p>}
        {banner.url ? (
          <button type="button" className="license-primary" onClick={() => void handleInstall()} disabled={installing}>
            {installing ? "正在下载安装包..." : "立即更新"}
          </button>
        ) : (
          <p className="error">管理员尚未配置下载地址，请联系客服获取安装包。</p>
        )}
        {!banner.force && (
          <button
            type="button"
            className="secondary"
            onClick={() => {
              dismiss(banner.remote);
              setBanner(null);
            }}
            disabled={installing}
          >
            稍后
          </button>
        )}
      </div>
    </div>
  );
}

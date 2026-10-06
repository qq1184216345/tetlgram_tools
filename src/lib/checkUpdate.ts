import { getLicenseApiBase } from "../api/license";
import {
  AppVersionManifest,
  isNewerVersion,
  manifestDownloadUrl,
  manifestForce,
} from "./appVersion";

export type UpdateCheckResult =
  | { status: "latest"; local: string; remote: string }
  | {
      status: "available";
      local: string;
      remote: string;
      notes: string;
      url: string;
      force: boolean;
      manifest: AppVersionManifest;
    }
  | { status: "error"; message: string };

export async function fetchAppVersionManifest(): Promise<AppVersionManifest> {
  const base = getLicenseApiBase();
  const resp = await fetch(`${base}/app/version`, { cache: "no-store" });
  if (!resp.ok) throw new Error(`更新源不可用 HTTP ${resp.status}`);
  return (await resp.json()) as AppVersionManifest;
}

export async function checkForAppUpdate(localVersion: string): Promise<UpdateCheckResult> {
  const local = String(localVersion || "").trim() || "0.0.0";
  try {
    const manifest = await fetchAppVersionManifest();
    const remote = String(manifest.version || "").trim();
    if (!remote) return { status: "error", message: "更新清单缺少 version 字段" };
    if (!isNewerVersion(remote, local)) {
      return { status: "latest", local, remote };
    }
    return {
      status: "available",
      local,
      remote,
      notes: String(manifest.notes || "").trim(),
      url: manifestDownloadUrl(manifest),
      force: manifestForce(manifest),
      manifest,
    };
  } catch (e) {
    return {
      status: "error",
      message: e instanceof Error ? e.message : "检查更新失败",
    };
  }
}

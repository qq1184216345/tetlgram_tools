import { invoke } from "@tauri-apps/api/core";

function runningInTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/** 下载官方安装包并启动安装程序。开发浏览器里则打开下载地址。 */
export async function startAppUpdate(url: string): Promise<void> {
  const target = url.trim();
  if (!target) {
    throw new Error("没有可用的下载地址");
  }
  if (!runningInTauri()) {
    window.open(target, "_blank", "noopener,noreferrer");
    return;
  }
  await invoke("install_update", { url: target });
}

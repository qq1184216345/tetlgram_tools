import { useEffect, useRef } from "react";

function isTauriRuntime() {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export function useTauriFileDrop(
  enabled: boolean,
  onDrop: (paths: string[]) => void,
  onHoverChange?: (over: boolean) => void,
) {
  const onDropRef = useRef(onDrop);
  const onHoverRef = useRef(onHoverChange);
  onDropRef.current = onDrop;
  onHoverRef.current = onHoverChange;

  useEffect(() => {
    if (!enabled || !isTauriRuntime()) return;
    let cancelled = false;
    let unlisten: (() => void) | undefined;

    void (async () => {
      const { getCurrentWebview } = await import("@tauri-apps/api/webview");
      if (cancelled) return;
      unlisten = await getCurrentWebview().onDragDropEvent((event) => {
        const payload = event.payload;
        if (payload.type === "leave") {
          onHoverRef.current?.(false);
          return;
        }
        if (payload.type === "enter" || payload.type === "over") {
          onHoverRef.current?.(true);
          return;
        }
        if (payload.type === "drop") {
          onHoverRef.current?.(false);
          onDropRef.current(payload.paths ?? []);
        }
      });
    })();

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [enabled]);
}

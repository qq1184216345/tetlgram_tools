import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  ReactNode,
} from "react";

type ToastType = "info" | "success" | "error";

interface ToastItem {
  id: string;
  type: ToastType;
  text: string;
}

interface ToastApi {
  info: (text: string) => void;
  success: (text: string) => void;
  error: (text: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const TOAST_DURATION_MS = 3500;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const show = useCallback(
    (type: ToastType, text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev, { id, type, text: trimmed }]);
      window.setTimeout(() => dismiss(id), TOAST_DURATION_MS);
    },
    [dismiss],
  );

  const toast = useMemo<ToastApi>(
    () => ({
      info: (text) => show("info", text),
      success: (text) => show("success", text),
      error: (text) => show("error", text),
    }),
    [show],
  );

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="toast-container" aria-live="polite">
        {toasts.map((item) => (
          <div key={item.id} className={`toast toast-${item.type}`} role="status">
            {item.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}

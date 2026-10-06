import { useCallback, useState } from "react";
import { ACCOUNTS_STORAGE_KEY } from "../lib/labels";

function loadIds(): string[] {
  try {
    const raw = localStorage.getItem(ACCOUNTS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is string => typeof item === "string" && item.trim() !== "");
  } catch {
    return [];
  }
}

export function usePersistedAccounts() {
  const [selected, setSelected] = useState<string[]>(loadIds);

  const onChange = useCallback((ids: string[]) => {
    setSelected(ids);
    try {
      localStorage.setItem(ACCOUNTS_STORAGE_KEY, JSON.stringify(ids));
    } catch {
      /* ignore */
    }
  }, []);

  return [selected, onChange] as const;
}

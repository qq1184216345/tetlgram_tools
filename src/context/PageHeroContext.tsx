import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  ReactNode,
} from "react";
import { PageId } from "../types";

type PageHeroContextValue = {
  actions: Partial<Record<PageId, ReactNode>>;
  setPageAction: (page: PageId, node: ReactNode | null) => void;
};

const PageHeroContext = createContext<PageHeroContextValue | null>(null);

export function PageHeroProvider({ children }: { children: ReactNode }) {
  const [actions, setActions] = useState<Partial<Record<PageId, ReactNode>>>({});

  const setPageAction = useCallback((page: PageId, node: ReactNode | null) => {
    setActions((prev) => {
      if (!node) {
        if (!(page in prev)) return prev;
        const next = { ...prev };
        delete next[page];
        return next;
      }
      return { ...prev, [page]: node };
    });
  }, []);

  const value = useMemo(
    () => ({ actions, setPageAction }),
    [actions, setPageAction],
  );

  return <PageHeroContext.Provider value={value}>{children}</PageHeroContext.Provider>;
}

export function usePageHeroAction(page: PageId) {
  const ctx = useContext(PageHeroContext);
  return ctx?.actions[page] ?? null;
}

export function useRegisterPageAction(page: PageId, onClick: () => void, label: string) {
  const setPageAction = useContext(PageHeroContext)?.setPageAction;
  const onClickRef = useRef(onClick);
  onClickRef.current = onClick;

  useEffect(() => {
    if (!setPageAction) return;
    setPageAction(
      page,
      <button type="button" className="page-hero-action" onClick={() => onClickRef.current()}>
        {label}
      </button>,
    );
    return () => setPageAction(page, null);
  }, [setPageAction, page, label]);
}

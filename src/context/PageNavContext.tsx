import { createContext, useContext } from "react";
import { PageId } from "../types";

const PageNavContext = createContext<(page: PageId) => void>(() => {});

export const PageNavProvider = PageNavContext.Provider;

export function usePageNav() {
  return useContext(PageNavContext);
}

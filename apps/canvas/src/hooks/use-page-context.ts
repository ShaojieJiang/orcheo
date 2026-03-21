/**
 * Hook for accessing the browser context from page components.
 */

import { createContext, useContext } from "react";

interface PageContext {
  page: "gallery" | "canvas" | "other";
  workflowId?: string | null;
  workflowName?: string | null;
}

interface BrowserContextValue {
  setPageContext: (ctx: PageContext) => void;
}

export const BrowserContext = createContext<BrowserContextValue>({
  setPageContext: () => {},
});

export function usePageContext(): BrowserContextValue {
  return useContext(BrowserContext);
}

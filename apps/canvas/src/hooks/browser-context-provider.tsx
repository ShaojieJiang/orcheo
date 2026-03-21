/**
 * BrowserContextProvider — wraps the app to relay Canvas page context
 * to the local `orcheo browser-aware` HTTP server.
 */

import type { ReactNode } from "react";
import { useBrowserContext } from "@/hooks/use-browser-context";
import { BrowserContext } from "@/hooks/use-page-context";

export function BrowserContextProvider({ children }: { children: ReactNode }) {
  const { setPageContext } = useBrowserContext();
  return (
    <BrowserContext.Provider value={{ setPageContext }}>
      {children}
    </BrowserContext.Provider>
  );
}

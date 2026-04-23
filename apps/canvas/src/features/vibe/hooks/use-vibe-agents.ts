import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getExternalAgents, type ExternalAgentProviderStatus } from "@/lib/api";
import { VIBE_AGENT_POLL_INTERVAL_MS } from "@features/vibe/constants";

const AGENTS_CACHE_KEY = "orcheo:vibe-agents-cache";
const TRANSIENT_STATES = new Set(["connecting", "refreshing", "checking"]);

const readCachedProviders = (): ExternalAgentProviderStatus[] => {
  try {
    const raw = sessionStorage.getItem(AGENTS_CACHE_KEY);
    return raw ? (JSON.parse(raw) as ExternalAgentProviderStatus[]) : [];
  } catch {
    return [];
  }
};

const writeCachedProviders = (
  providers: ExternalAgentProviderStatus[],
): void => {
  try {
    sessionStorage.setItem(AGENTS_CACHE_KEY, JSON.stringify(providers));
  } catch {
    // Silently ignore storage errors.
  }
};

export function useVibeAgents() {
  const [providers, setProviders] =
    useState<ExternalAgentProviderStatus[]>(readCachedProviders);
  const [isLoading, setIsLoading] = useState(true);
  const mountedRef = useRef(true);

  const fetchAgents = useCallback(async () => {
    try {
      const response = await getExternalAgents();
      if (mountedRef.current) {
        setProviders((prev) => {
          // Keep previously-ready providers alive during transient backend states
          // to avoid flickering "No agents connected" in the Vibe sidebar.
          const merged = response.providers.map((next) => {
            if (TRANSIENT_STATES.has(next.state)) {
              const prevProvider = prev.find(
                (p) => p.provider === next.provider,
              );
              return prevProvider ?? next;
            }
            return next;
          });
          writeCachedProviders(merged);
          return merged;
        });
      }
    } catch {
      // Silently ignore — agents may be unavailable.
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void fetchAgents();

    const interval = setInterval(() => {
      void fetchAgents();
    }, VIBE_AGENT_POLL_INTERVAL_MS);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchAgents]);

  const readyProviders = useMemo(
    () => providers.filter((p) => p.state === "ready"),
    [providers],
  );

  return { providers, readyProviders, isLoading, refresh: fetchAgents };
}

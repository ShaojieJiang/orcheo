import { useCallback, useEffect, useRef, useState } from "react";
import { getExternalAgents, type ExternalAgentProviderStatus } from "@/lib/api";
import { VIBE_AGENT_POLL_INTERVAL_MS } from "@features/vibe/constants";

export function useVibeAgents() {
  const [providers, setProviders] = useState<ExternalAgentProviderStatus[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const mountedRef = useRef(true);

  const fetchAgents = useCallback(async () => {
    try {
      const response = await getExternalAgents();
      if (mountedRef.current) {
        setProviders(response.providers);
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

  const readyProviders = providers.filter((p) => p.state === "ready");

  return { providers, readyProviders, isLoading, refresh: fetchAgents };
}

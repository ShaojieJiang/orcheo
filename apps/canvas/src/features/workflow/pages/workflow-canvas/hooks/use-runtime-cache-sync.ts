import { useEffect } from "react";
import type { MutableRefObject } from "react";

import {
  clearRuntimeCacheFromSession,
  persistRuntimeCacheToSession,
  readRuntimeCacheFromSession,
} from "@features/workflow/pages/workflow-canvas/helpers/runtime-cache";

interface UseRuntimeCacheSyncParams<TCache> {
  runtimeCacheKey: string;
  nodeRuntimeCache: TCache;
  setNodeRuntimeCache: (value: TCache) => void;
  previousRuntimeCacheKeyRef: MutableRefObject<string>;
}

export function useRuntimeCacheSync<TCache>({
  runtimeCacheKey,
  nodeRuntimeCache,
  setNodeRuntimeCache,
  previousRuntimeCacheKeyRef,
}: UseRuntimeCacheSyncParams<TCache>) {
  useEffect(() => {
    if (previousRuntimeCacheKeyRef.current !== runtimeCacheKey) {
      clearRuntimeCacheFromSession(previousRuntimeCacheKeyRef.current);
      previousRuntimeCacheKeyRef.current = runtimeCacheKey;
      setNodeRuntimeCache(
        readRuntimeCacheFromSession(runtimeCacheKey) as TCache,
      );
    }
  }, [runtimeCacheKey, previousRuntimeCacheKeyRef, setNodeRuntimeCache]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const handle = window.setTimeout(() => {
      persistRuntimeCacheToSession(runtimeCacheKey, nodeRuntimeCache);
    }, 200);

    return () => {
      window.clearTimeout(handle);
    };
  }, [nodeRuntimeCache, runtimeCacheKey]);

  useEffect(() => {
    return () => {
      clearRuntimeCacheFromSession(runtimeCacheKey);
    };
  }, [runtimeCacheKey]);
}

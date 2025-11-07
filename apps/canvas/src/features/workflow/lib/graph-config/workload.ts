import {
  LARGE_DATASET_THRESHOLD,
  YIELD_BATCH_SIZE,
} from "@features/workflow/lib/graph-config/constants";
import type { MaybeYieldFn } from "@features/workflow/lib/graph-config/types";

const yieldToMainThread = async () =>
  new Promise<void>((resolve) => {
    setTimeout(resolve, 0);
  });

export const createYieldController = (
  totalWorkItems: number,
): { maybeYield: MaybeYieldFn } => {
  const shouldYieldProcessing = totalWorkItems > LARGE_DATASET_THRESHOLD;
  let processedItems = 0;

  const maybeYield: MaybeYieldFn = async () => {
    if (!shouldYieldProcessing) {
      return;
    }
    processedItems += 1;
    if (processedItems % YIELD_BATCH_SIZE === 0) {
      await yieldToMainThread();
    }
  };

  return { maybeYield };
};

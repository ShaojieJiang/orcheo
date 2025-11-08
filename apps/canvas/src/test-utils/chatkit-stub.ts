import type { ReactNode } from "react";

export const ChatKit = () => null;

export const ChatKitProvider = ({ children }: { children?: ReactNode }) =>
  children ?? null;

export const useChatKit = (options: unknown = {}) => ({
  control: {
    setInstance: () => undefined,
    options,
    handlers: {},
  },
  ref: { current: null },
  focusComposer: () => undefined,
  setThreadId: () => undefined,
  sendUserMessage: async () => undefined,
  setComposerValue: () => undefined,
  fetchUpdates: async () => undefined,
  sendCustomAction: async () => undefined,
});

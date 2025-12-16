import type { ReactNode } from "react";

export const ChatKit = () => null;

export const ChatKitProvider = ({ children }: { children?: ReactNode }) =>
  children ?? null;

export const useChatKit = () => ({
  control: {
    setInstance: () => undefined,
    options: {},
    handlers: {},
  },
  focusComposer: async () => undefined,
  setThreadId: async () => undefined,
  sendUserMessage: async () => undefined,
  setComposerValue: async () => undefined,
  fetchUpdates: async () => undefined,
  sendCustomAction: async () => undefined,
  ref: { current: null },
});

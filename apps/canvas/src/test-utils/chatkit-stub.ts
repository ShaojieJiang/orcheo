import type { ReactNode } from "react";

export const ChatKit = () => null;

export const ChatKitProvider = ({ children }: { children?: ReactNode }) =>
  children ?? null;

export const useChatKit = () => ({
  status: "disconnected" as const,
  connect: async () => undefined,
  disconnect: async () => undefined,
  sendMessage: async () => undefined,
  conversations: [],
  messages: [],
});

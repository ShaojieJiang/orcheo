import type { ReactNode } from "react";
import { vi } from "vitest";

vi.mock("@openai/chatkit-react", () => ({
  ChatKit: () => null,
  ChatKitProvider: ({ children }: { children?: ReactNode }) => children ?? null,
  useChatKit: () => ({
    status: "disconnected",
    connect: vi.fn(),
    disconnect: vi.fn(),
    sendMessage: vi.fn(),
    conversations: [],
  }),
}));

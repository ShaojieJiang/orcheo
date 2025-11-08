import { vi } from "vitest";

vi.mock("@openai/chatkit-react", async () => ({
  ...(await import("@/test-utils/chatkit-stub")),
}));

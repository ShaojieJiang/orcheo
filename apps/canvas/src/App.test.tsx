import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import {
  act,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "./App";
import { useWorkflowStore } from "./store/workflowStore";
import type { CredentialTemplateSummary } from "./types";

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  public onopen: ((event: Event) => void) | null = null;
  public onclose: ((event: Event) => void) | null = null;
  public onerror: ((event: Event) => void) | null = null;
  public onmessage: ((event: MessageEvent) => void) | null = null;

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }

  close(): void {
    if (this.onclose) {
      this.onclose(new Event("close"));
    }
  }

  send(): void {
    // no-op for tests
  }
}

const mockFetch = vi.fn<Parameters<typeof fetch>, ReturnType<typeof fetch>>();

beforeAll(() => {
  (globalThis as { ResizeObserver?: typeof ResizeObserver }).ResizeObserver =
    class {
      observe(): void {}
      unobserve(): void {}
      disconnect(): void {}
    };
  (globalThis as unknown as { WebSocket: typeof WebSocket }).WebSocket =
    MockWebSocket as unknown as typeof WebSocket;
  if (typeof crypto.randomUUID !== "function") {
    (crypto as Crypto & { randomUUID: () => string }).randomUUID = () =>
      "00000000-0000-0000-0000-000000000000";
  }
});

beforeEach(() => {
  mockFetch.mockReset();
  (globalThis as { fetch: typeof fetch }).fetch = mockFetch as unknown as typeof fetch;
  localStorage.clear();

  const baseState = useWorkflowStore.getState();
  const clonedNodes = baseState.nodes.map((node) => ({
    ...node,
    data: { ...node.data },
    position: { ...node.position },
  }));
  const clonedEdges = baseState.edges.map((edge) => ({ ...edge }));

  useWorkflowStore.setState(
    {
      nodes: clonedNodes,
      edges: clonedEdges,
      searchTerm: "",
      savedGraph: null,
      lastDiff: [],
      undoStack: [],
      redoStack: [],
      selectedNodeId: "trigger",
      credentialTemplates: [],
      credentialAlerts: [],
      subWorkflows: [],
      executionEvents: [],
      websocketStatus: "disconnected",
      chatTranscript: [],
    },
    false,
  );
  MockWebSocket.instances = [];
});

afterEach(() => {
  vi.clearAllMocks();
});

function mockResponse<T>(data: T, ok = true): Promise<Response> {
  return Promise.resolve({
    ok,
    json: async () => data,
  } as Response);
}

describe("App", () => {
  it("renders the primary canvas layout", async () => {
    mockFetch.mockImplementation(() => mockResponse<[]>([]));

    render(<App />);

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());

    expect(screen.getByRole("heading", { name: /Node Library/i })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Workflow Operations/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Execution Monitor/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Workflow Chat/i }),
    ).toBeInTheDocument();
  });

  it("allows issuing credentials and surfaces alerts", async () => {
    const template = {
      id: "api-key",
      name: "API Key",
      provider: "Example",
      description: "",
      scopes: ["read"],
      fields: [
        {
          name: "token",
          description: "API Token",
          optional: false,
          secret: true,
        },
      ],
    } satisfies CredentialTemplateSummary;

    mockFetch
      .mockImplementationOnce(() => mockResponse([template]))
      .mockImplementationOnce(() =>
        mockResponse({ alerts: [{ message: "Rotate keys soon", severity: "info" }] }),
      );

    render(<App />);

    const tokenField = await screen.findByPlaceholderText(/Required/i);
    await userEvent.type(tokenField, "super-secret");
    await userEvent.click(screen.getByRole("button", { name: /Issue Credential/i }));

    await waitFor(() =>
      expect(screen.getByText(/INFO: Rotate keys soon/i)).toBeInTheDocument(),
    );
  });

  it("connects and disconnects the execution monitor websocket", async () => {
    mockFetch.mockImplementation(() => mockResponse<[]>([]));

    const user = userEvent.setup();
    render(<App />);

    const workflowInput = screen.getByPlaceholderText(/Workflow ID/i);
    await user.type(workflowInput, "wf-123");
    await user.click(screen.getByRole("button", { name: "Connect" }));

    expect(screen.getByText(/connecting/i)).toBeInTheDocument();

    const instance = MockWebSocket.instances.at(-1);
    await act(async () => {
      instance?.onopen?.(new Event("open"));
    });

    expect(screen.getByText(/connected/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(screen.getByText(/disconnected/i)).toBeInTheDocument();
  });

  it("validates workflows before publishing", async () => {
    mockFetch.mockImplementation(() => mockResponse<[]>([]));

    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: /Publish/i }));

    expect(
      screen.getByText(/Resolve validation errors before publishing/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Add an output node to handoff results/i),
    ).toBeInTheDocument();
  });
});

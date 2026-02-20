import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { TraceViewerData } from "@features/workflow/components/trace/agent-prism";
import type { TraceTabContentProps } from "./trace-tab-content";

import { TraceTabContent } from "./trace-tab-content";

vi.mock(
  "@features/workflow/components/trace/agent-prism/theme/theme.css",
  () => ({}),
  { virtual: true },
);

const traceViewerMock = vi.hoisted(() => vi.fn());

vi.mock("@features/workflow/components/trace/agent-prism", () => ({
  TraceViewer: traceViewerMock,
}));

const sampleViewerData: TraceViewerData = {
  traceRecord: {
    id: "exec-1",
    name: "Trace 1",
    spansCount: 3,
    durationMs: 1200,
    agentDescription: "success",
    totalTokens: 42,
    startTime: Date.now(),
  },
  spans: [],
};

const createProps = (
  overrides: Partial<TraceTabContentProps> = {},
): TraceTabContentProps => ({
  status: "ready",
  error: undefined,
  viewerData: [sampleViewerData],
  activeViewer: sampleViewerData,
  onRefresh: vi.fn(),
  isRefreshing: false,
  onSelectTrace: vi.fn(),
  summary: undefined,
  lastUpdatedAt: undefined,
  isLive: false,
  ...overrides,
});

describe("TraceTabContent", () => {
  beforeEach(() => {
    traceViewerMock.mockImplementation(
      ({
        data,
        activeTraceId,
      }: {
        data: TraceViewerData[];
        activeTraceId?: string;
      }) => (
        <div data-testid="trace-viewer">
          <span data-testid="trace-viewer-count">
            {Array.isArray(data) ? data.length : 0}
          </span>
          <span data-testid="trace-viewer-active-id">
            {activeTraceId ?? "none"}
          </span>
        </div>
      ),
    );
    vi.spyOn(window, "open").mockImplementation(() => null);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    traceViewerMock.mockReset();
  });

  it("shows loading skeleton when trace is loading", () => {
    const { container } = render(
      <TraceTabContent
        {...createProps({
          status: "loading",
          viewerData: [],
          activeViewer: undefined,
        })}
      />,
    );

    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(
      0,
    );
    expect(screen.queryByTestId("trace-viewer")).not.toBeInTheDocument();
  });

  it("renders error alert when trace fails to load", () => {
    render(
      <TraceTabContent
        {...createProps({
          status: "error",
          error: "Server unavailable",
          viewerData: [],
          activeViewer: undefined,
        })}
      />,
    );

    expect(screen.getByText(/unable to load trace/i)).toBeInTheDocument();
    expect(screen.getByText(/server unavailable/i)).toBeInTheDocument();
  });

  it("renders viewer and summary when data is available", () => {
    render(
      <TraceTabContent
        {...createProps({
          summary: { spanCount: 5, totalTokens: 84 },
          lastUpdatedAt: "2024-01-01T12:00:00Z",
        })}
      />,
    );

    expect(screen.getByTestId("trace-viewer")).toBeInTheDocument();
    expect(screen.getByTestId("trace-viewer-count")).toHaveTextContent("1");
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("84")).toBeInTheDocument();
  });

  it("passes the active trace id to the viewer", () => {
    render(
      <TraceTabContent
        {...createProps({
          summary: { spanCount: 2, totalTokens: 10 },
        })}
      />,
    );

    expect(screen.getByTestId("trace-viewer-active-id")).toHaveTextContent(
      sampleViewerData.traceRecord.id,
    );
  });

  it("calls refresh handler when refresh button is clicked", async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    render(
      <TraceTabContent
        {...createProps({
          onRefresh,
          summary: { spanCount: 1, totalTokens: 10 },
          isLive: true,
        })}
      />,
    );

    const [refreshButton] = screen.getAllByRole("button", { name: /refresh/i });
    await user.click(refreshButton);
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("invokes onSelectTrace when the viewer requests a trace change", () => {
    const onSelectTrace = vi.fn();
    traceViewerMock.mockImplementation(
      ({
        onTraceSelect,
      }: {
        onTraceSelect?: (trace: TraceViewerData["traceRecord"]) => void;
      }) => (
        <div data-testid="trace-viewer">
          <button
            type="button"
            onClick={() => {
              onTraceSelect?.(sampleViewerData.traceRecord);
            }}
          >
            select-trace
          </button>
        </div>
      ),
    );

    const { getByRole } = render(
      <TraceTabContent
        {...createProps({
          onSelectTrace,
          summary: { spanCount: 1, totalTokens: 10 },
        })}
      />,
    );

    getByRole("button", { name: /select-trace/i }).click();

    expect(onSelectTrace).toHaveBeenCalledWith(sampleViewerData.traceRecord.id);
  });
});

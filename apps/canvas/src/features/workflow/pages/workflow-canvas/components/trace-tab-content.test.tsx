import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { TraceViewerData } from "@features/workflow/components/trace/agent-prism";

import { TraceTabContent } from "./trace-tab-content";

vi.mock(
  "@features/workflow/components/trace/agent-prism/theme/theme.css",
  () => ({}),
  { virtual: true },
);

vi.mock("@features/workflow/components/trace/agent-prism", () => ({
  TraceViewer: ({ data }: { data: unknown }) => (
    <div data-testid="trace-viewer">
      {Array.isArray(data) ? data.length : 0}
    </div>
  ),
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

describe("TraceTabContent", () => {
  beforeEach(() => {
    vi.spyOn(window, "open").mockImplementation(() => null);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows loading skeleton when trace is loading", () => {
    const { container } = render(
      <TraceTabContent
        status="loading"
        error={undefined}
        viewerData={[]}
        activeViewer={undefined}
        onRefresh={vi.fn()}
        summary={undefined}
        lastUpdatedAt={undefined}
        isLive={false}
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
        status="error"
        error="Server unavailable"
        viewerData={[]}
        activeViewer={undefined}
        onRefresh={vi.fn()}
        summary={undefined}
        lastUpdatedAt={undefined}
        isLive={false}
      />,
    );

    expect(screen.getByText(/unable to load trace/i)).toBeInTheDocument();
    expect(screen.getByText(/server unavailable/i)).toBeInTheDocument();
  });

  it("renders viewer and summary when data is available", () => {
    render(
      <TraceTabContent
        status="ready"
        error={undefined}
        viewerData={[sampleViewerData]}
        activeViewer={sampleViewerData}
        onRefresh={vi.fn()}
        summary={{ spanCount: 5, totalTokens: 84 }}
        lastUpdatedAt="2024-01-01T12:00:00Z"
        isLive={false}
      />,
    );

    expect(screen.getByTestId("trace-viewer")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("84")).toBeInTheDocument();
  });

  it("calls refresh handler when refresh button is clicked", async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    render(
      <TraceTabContent
        status="ready"
        error={undefined}
        viewerData={[sampleViewerData]}
        activeViewer={sampleViewerData}
        onRefresh={onRefresh}
        summary={{ spanCount: 1, totalTokens: 10 }}
        lastUpdatedAt={undefined}
        isLive
      />,
    );

    const [refreshButton] = screen.getAllByRole("button", { name: /refresh/i });
    await user.click(refreshButton);
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});

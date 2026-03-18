import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { WorkflowCanvasLayout } from "./workflow-canvas-layout";

vi.mock("@features/shared/components/top-navigation", () => ({
  default: () => <div data-testid="top-navigation" />,
}));

vi.mock("@features/workflow/components/panels/workflow-tabs", () => ({
  default: () => <div data-testid="workflow-tabs" />,
}));

vi.mock("@features/chatkit/components/canvas-chat-bubble", () => ({
  CanvasChatBubble: () => <div data-testid="chat-bubble" />,
}));

vi.mock(
  "@features/workflow/pages/workflow-canvas/components/workflow-tab-content",
  () => ({
    WorkflowTabContent: () => <div>workflow-panel</div>,
  }),
);

vi.mock(
  "@features/workflow/pages/workflow-canvas/components/trace-tab-content",
  () => ({
    TraceTabContent: () => <div>trace-panel</div>,
  }),
);

vi.mock(
  "@features/workflow/pages/workflow-canvas/components/readiness-tab-content",
  () => ({
    ReadinessTabContent: () => <div>readiness-panel</div>,
  }),
);

vi.mock(
  "@features/workflow/pages/workflow-canvas/components/settings-tab-content",
  () => ({
    SettingsTabContent: () => <div>settings-panel</div>,
  }),
);

describe("WorkflowCanvasLayout", () => {
  it("keeps the workflow tab mounted but hidden when trace is active", () => {
    render(
      <WorkflowCanvasLayout
        topNavigationProps={
          {
            currentWorkflow: { name: "Workflow", id: "wf-1" },
          } as never
        }
        tabsProps={{
          activeTab: "trace",
          onTabChange: vi.fn(),
          readinessAlertCount: 0,
        }}
        workflowProps={{} as never}
        traceProps={{} as never}
        readinessProps={{} as never}
        settingsProps={{} as never}
        chat={null}
      />,
    );

    const workflowPanel = screen
      .getByText("workflow-panel")
      .closest('[role="tabpanel"]');

    expect(workflowPanel).toHaveAttribute("data-state", "inactive");
    expect(workflowPanel).toHaveClass("data-[state=inactive]:hidden");
    expect(screen.getByText("trace-panel")).toBeInTheDocument();
  });
});

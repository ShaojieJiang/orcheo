import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WorkflowGalleryTabs } from "./workflow-gallery-tabs";

vi.mock("./workflow-card", () => ({
  WorkflowCard: () => <div data-testid="workflow-card" />,
}));

describe("WorkflowGalleryTabs", () => {
  it("shows a loading screen while workflows are being fetched", () => {
    render(
      <WorkflowGalleryTabs
        selectedTab="all"
        onSelectedTabChange={vi.fn()}
        isLoading
        sortedWorkflows={[]}
        isTemplateView={false}
        searchQuery=""
        onImportStarterPack={vi.fn()}
        onOpenWorkflow={vi.fn()}
        onUseTemplate={vi.fn()}
        onExportWorkflow={vi.fn()}
        onDeleteWorkflow={vi.fn()}
      />,
    );

    expect(screen.getByText(/loading workflows/i)).toBeTruthy();
    expect(screen.queryByText(/import starter pack/i)).toBeNull();
  });
});

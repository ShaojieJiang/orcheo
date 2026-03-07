import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import WorkflowBreadcrumbs from "@/features/shared/components/top-navigation/workflow-breadcrumbs";

describe("WorkflowBreadcrumbs", () => {
  it("renders workflow name once when path already includes it", () => {
    render(
      <MemoryRouter>
        <WorkflowBreadcrumbs
          currentWorkflow={{
            name: "Simple Agent Copy",
            path: ["Projects", "Workflows", "Simple Agent Copy"],
          }}
          windowWidth={1280}
        />
      </MemoryRouter>,
    );

    expect(screen.getAllByText("Simple Agent Copy")).toHaveLength(1);
  });
});

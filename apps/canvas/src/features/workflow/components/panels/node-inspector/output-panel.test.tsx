import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OutputPanel } from "./output-panel";

vi.mock("@/design-system/ui/tabs", () => ({
  Tabs: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsContent: ({
    children,
    value,
  }: {
    children: ReactNode;
    value: string;
  }) => <div data-testid={value}>{children}</div>,
  TabsList: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsTrigger: ({ children }: { children: ReactNode }) => (
    <button type="button">{children}</button>
  ),
}));

describe("OutputPanel", () => {
  it("marks test output as selectable text", () => {
    render(
      <OutputPanel
        outputViewMode="output-json"
        onOutputViewModeChange={() => undefined}
        useLiveData={false}
        onToggleLiveData={() => undefined}
        runtime={null}
        formattedUpdatedAt={null}
        testResult={{ ok: true }}
        testError={null}
        hasRuntime={false}
        hasLiveOutputs={false}
        outputDisplay={undefined}
      />,
    );

    expect(screen.getByText(/"ok": true/).closest("pre")).toHaveClass(
      "select-text",
    );
  });
});

import { describe, expect, it, vi } from "vitest";
import { createEvent, fireEvent, render } from "@testing-library/react";
import { useWorkflowKeybindings } from "./use-workflow-keybindings";

function TestHarness({
  copySelectedNodes,
  pasteNodes,
}: {
  copySelectedNodes: () => Promise<void>;
  pasteNodes: () => Promise<void>;
}) {
  useWorkflowKeybindings({
    nodesRef: { current: [] },
    deleteNodes: vi.fn(),
    handleUndo: vi.fn(),
    handleRedo: vi.fn(),
    copySelectedNodes,
    cutSelectedNodes: vi.fn().mockResolvedValue(undefined),
    pasteNodes,
  });

  return <div>Copy this toast text</div>;
}

describe("useWorkflowKeybindings", () => {
  it("does not hijack copy shortcuts", () => {
    const copySelectedNodes = vi.fn().mockResolvedValue(undefined);

    render(
      <TestHarness
        copySelectedNodes={copySelectedNodes}
        pasteNodes={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    fireEvent.keyDown(document, { key: "c", metaKey: true });

    expect(copySelectedNodes).not.toHaveBeenCalled();
  });

  it("does not hijack paste shortcuts", () => {
    const pasteNodes = vi.fn().mockResolvedValue(undefined);

    render(
      <TestHarness
        copySelectedNodes={vi.fn().mockResolvedValue(undefined)}
        pasteNodes={pasteNodes}
      />,
    );

    fireEvent.keyDown(document, { key: "v", metaKey: true });

    expect(pasteNodes).not.toHaveBeenCalled();
  });

  it("does not hijack the browser find shortcut", () => {
    render(
      <TestHarness
        copySelectedNodes={vi.fn().mockResolvedValue(undefined)}
        pasteNodes={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    const event = createEvent.keyDown(document, {
      key: "f",
      metaKey: true,
    });
    fireEvent(document, event);

    expect(event.defaultPrevented).toBe(false);
  });
});

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render } from "@testing-library/react";
import { useWorkflowKeybindings } from "./use-workflow-keybindings";

function TestHarness({
  copySelectedNodes,
  pasteNodes,
  setIsSearchOpen,
}: {
  copySelectedNodes: () => Promise<void>;
  pasteNodes: () => Promise<void>;
  setIsSearchOpen: (value: boolean) => void;
}) {
  useWorkflowKeybindings({
    nodesRef: { current: [] },
    deleteNodes: vi.fn(),
    handleUndo: vi.fn(),
    handleRedo: vi.fn(),
    copySelectedNodes,
    cutSelectedNodes: vi.fn().mockResolvedValue(undefined),
    pasteNodes,
    setIsSearchOpen,
    setSearchMatches: vi.fn(),
    setCurrentSearchIndex: vi.fn(),
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
        setIsSearchOpen={vi.fn()}
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
        setIsSearchOpen={vi.fn()}
      />,
    );

    fireEvent.keyDown(document, { key: "v", metaKey: true });

    expect(pasteNodes).not.toHaveBeenCalled();
  });

  it("still opens search on the find shortcut", () => {
    const setIsSearchOpen = vi.fn();

    render(
      <TestHarness
        copySelectedNodes={vi.fn().mockResolvedValue(undefined)}
        pasteNodes={vi.fn().mockResolvedValue(undefined)}
        setIsSearchOpen={setIsSearchOpen}
      />,
    );

    fireEvent.keyDown(document, { key: "f", metaKey: true });

    expect(setIsSearchOpen).toHaveBeenCalledWith(true);
  });
});

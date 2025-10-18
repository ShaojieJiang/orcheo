import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { App } from "./App";

describe("App", () => {
  it("adds nodes and supports undo/redo", async () => {
    render(<App />);
    const addHttpRequest = screen.getByRole("button", { name: /Add HTTP Request/i });
    fireEvent.click(addHttpRequest);
    expect(screen.getAllByTestId("canvas-node")).toHaveLength(1);

    const undoButton = screen.getByRole("button", { name: /Undo/i });
    fireEvent.click(undoButton);
    await waitFor(() => {
      expect(screen.queryAllByTestId("canvas-node")).toHaveLength(0);
    });

    const redoButton = screen.getByRole("button", { name: /Redo/i });
    fireEvent.click(redoButton);
    expect(screen.getAllByTestId("canvas-node")).toHaveLength(1);
  });

  it("imports and exports workflow JSON", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /Add Webhook Trigger/i }));

    const exportButton = screen.getByRole("button", { name: /Export JSON/i });
    fireEvent.click(exportButton);
    const textarea = screen.getByLabelText(/Workflow JSON/i) as HTMLTextAreaElement;
    expect(textarea.value).toContain("Webhook Trigger");

    fireEvent.change(textarea, { target: { value: "[]" } });
    fireEvent.click(screen.getByRole("button", { name: /Import JSON/i }));
    expect(screen.queryAllByTestId("canvas-node")).toHaveLength(0);
  });

  it("logs workflow chat exchanges", () => {
    render(<App />);
    const textarea = screen.getByLabelText(/Ask the canvas copilot/i);
    fireEvent.change(textarea, { target: { value: "Run smoke tests" } });
    fireEvent.click(screen.getByRole("button", { name: /Send/i }));
    expect(screen.getByText(/Simulated hand-off response/)).toBeInTheDocument();
  });
});

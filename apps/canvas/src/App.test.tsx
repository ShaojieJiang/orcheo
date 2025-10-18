import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { App } from "./App";

describe("App", () => {
  it("renders node catalog and workflow controls", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /Orcheo Canvas/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Node Catalog/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Save/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Credential Templates/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Publish/i })).toBeInTheDocument();
  });
});

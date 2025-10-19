import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  it("renders the Orcheo Canvas navigation", () => {
    render(<App />);
    expect(screen.getByText(/Orcheo Canvas/i)).toBeInTheDocument();
  });
});

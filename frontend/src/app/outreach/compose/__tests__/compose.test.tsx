import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <div data-testid="markdown">{children}</div>,
}));

vi.mock("@/lib/api", () => ({
  generateReport: vi.fn(),
  fetchReportStatus: vi.fn(),
  createOutreachEvent: vi.fn(),
}));

import ComposePage from "../page";

describe("ComposePage — mode toggle", () => {
  it("renders both mode buttons", () => {
    render(<ComposePage />);
    expect(screen.getByTestId("mode-single")).toBeInTheDocument();
    expect(screen.getByTestId("mode-batch")).toBeInTheDocument();
  });

  it("starts in single mode", () => {
    render(<ComposePage />);
    expect(screen.getByTestId("mode-single")).toHaveStyle({ background: "#2563EB" });
    expect(screen.getByTestId("mode-batch")).toHaveStyle({ background: "#fff" });
  });

  it("switches to batch mode on click", () => {
    render(<ComposePage />);
    fireEvent.click(screen.getByTestId("mode-batch"));
    expect(screen.getByTestId("mode-batch")).toHaveStyle({ background: "#2563EB" });
    expect(screen.getByTestId("mode-single")).toHaveStyle({ background: "#fff" });
  });

  it("switches back to single mode from batch", () => {
    render(<ComposePage />);
    fireEvent.click(screen.getByTestId("mode-batch"));
    fireEvent.click(screen.getByTestId("mode-single"));
    expect(screen.getByTestId("mode-single")).toHaveStyle({ background: "#2563EB" });
  });

  it("clears recipients when switching modes", () => {
    render(<ComposePage />);
    fireEvent.change(screen.getByTestId("chip-company"), { target: { value: "Acme" } });
    fireEvent.click(screen.getByText("+"));
    expect(screen.getByTestId("chips").children.length).toBe(1);

    fireEvent.click(screen.getByTestId("mode-batch"));
    expect(screen.getByTestId("chips").children.length).toBe(0);
  });
});

describe("ComposePage — preview button disabled state", () => {
  it("preview button is disabled when no recipients", () => {
    render(<ComposePage />);
    expect(screen.getByTestId("btn-preview")).toBeDisabled();
  });

  it("preview button is enabled after adding a recipient", () => {
    render(<ComposePage />);
    fireEvent.change(screen.getByTestId("chip-company"), { target: { value: "Acme" } });
    fireEvent.click(screen.getByText("+"));
    expect(screen.getByTestId("btn-preview")).not.toBeDisabled();
  });

  it("preview button re-disables after removing the only recipient", () => {
    render(<ComposePage />);
    fireEvent.change(screen.getByTestId("chip-company"), { target: { value: "Acme" } });
    fireEvent.click(screen.getByText("+"));
    expect(screen.getByTestId("btn-preview")).not.toBeDisabled();

    fireEvent.click(screen.getByText("×"));
    expect(screen.getByTestId("btn-preview")).toBeDisabled();
  });

  it("single mode + button disables when one recipient already added", () => {
    render(<ComposePage />);
    fireEvent.change(screen.getByTestId("chip-company"), { target: { value: "Co A" } });
    fireEvent.click(screen.getByText("+"));

    fireEvent.change(screen.getByTestId("chip-company"), { target: { value: "Co B" } });
    expect(screen.getByText("+")).toBeDisabled();
  });

  it("batch mode allows multiple chips", () => {
    render(<ComposePage />);
    fireEvent.click(screen.getByTestId("mode-batch"));

    fireEvent.change(screen.getByTestId("chip-company"), { target: { value: "Co A" } });
    fireEvent.click(screen.getByText("+"));

    fireEvent.change(screen.getByTestId("chip-company"), { target: { value: "Co B" } });
    fireEvent.click(screen.getByText("+"));

    expect(screen.getByTestId("chips").children.length).toBe(2);
    expect(screen.getByTestId("btn-preview")).not.toBeDisabled();
  });
});

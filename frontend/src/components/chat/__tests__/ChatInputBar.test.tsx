import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatInputBar } from "../ChatInputBar";
import { SLASH_COMMANDS, type SlashCommand } from "@/components/ui/SlashCommandPopup";

vi.mock("next/navigation", () => ({
  useSearchParams: vi.fn(() => new URLSearchParams()),
}));

import { useSearchParams } from "next/navigation";

// P1-7 banner test: when the user types an exact C-class alias, a
// migration hint appears above the textarea. Other queries (including
// non-C aliases) must not trigger it. Banner copy lives in ChatInputBar
// itself; the data-testid is the public hook.

const FULL_COMMANDS: SlashCommand[] = SLASH_COMMANDS.map((c) => ({
  ...c,
  displayName: c.slug,
  description: "",
}));

function renderBar(input: string) {
  return render(
    <ChatInputBar
      input={input}
      onInputChange={() => {}}
      attachments={[]}
      onRemoveAttachment={() => {}}
      onPickFile={() => {}}
      uploading={false}
      isStreaming={false}
      slashParsing={false}
      onSend={() => {}}
      slashCommands={FULL_COMMANDS}
      slashActiveIndex={0}
      onSlashActiveIndexChange={() => {}}
      onSlashSelect={() => {}}
    />,
  );
}

const mockUseSearchParams = vi.mocked(useSearchParams);

beforeEach(() => {
  mockUseSearchParams.mockReturnValue(new URLSearchParams() as ReturnType<typeof useSearchParams>);
});

describe("<ChatInputBar /> context bar", () => {
  it("renders context bar when ?context= is present", () => {
    mockUseSearchParams.mockReturnValue(
      new URLSearchParams("context=outreach&company=Pfizer") as ReturnType<typeof useSearchParams>,
    );
    renderBar("");
    const bar = screen.getByTestId("context-bar");
    expect(bar).toBeInTheDocument();
    expect(bar.textContent).toContain("outreach");
    expect(bar.textContent).toContain("Pfizer");
  });

  it("does not render context bar when no ?context= param", () => {
    renderBar("");
    expect(screen.queryByTestId("context-bar")).not.toBeInTheDocument();
  });

  it("close button hides the context bar", () => {
    mockUseSearchParams.mockReturnValue(
      new URLSearchParams("context=outreach") as ReturnType<typeof useSearchParams>,
    );
    renderBar("");
    expect(screen.getByTestId("context-bar")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("context-bar-close"));
    expect(screen.queryByTestId("context-bar")).not.toBeInTheDocument();
  });
});

describe("<ChatInputBar /> migration banner", () => {
  it("shows the banner when input is exactly /email (a C-class alias)", () => {
    renderBar("/email");
    const banner = screen.getByTestId("slash-migration-banner");
    expect(banner).toBeInTheDocument();
    expect(banner.textContent).toContain("Outreach 工作台");
  });

  it("shows the banner for every C-class alias", () => {
    for (const alias of ["email", "batch-email", "log", "outreach", "import-reply"]) {
      const { unmount } = renderBar(`/${alias}`);
      expect(screen.queryByTestId("slash-migration-banner")).toBeInTheDocument();
      unmount();
    }
  });

  it("does not show the banner when input is /paper (an A-class alias)", () => {
    renderBar("/paper");
    expect(screen.queryByTestId("slash-migration-banner")).not.toBeInTheDocument();
  });

  it("does not show the banner when input does not start with a slash", () => {
    renderBar("email");
    expect(screen.queryByTestId("slash-migration-banner")).not.toBeInTheDocument();
  });

  it("does not show the banner when input is just /", () => {
    renderBar("/");
    expect(screen.queryByTestId("slash-migration-banner")).not.toBeInTheDocument();
  });
});

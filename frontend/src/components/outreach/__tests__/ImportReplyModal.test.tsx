import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ImportReplyModal } from "../ImportReplyModal";

vi.mock("@/lib/api", () => ({
  generateReport: vi.fn(),
  fetchReportStatus: vi.fn(),
  createOutreachEvent: vi.fn(),
}));

import * as api from "@/lib/api";

const mockedGenerate = vi.mocked(api.generateReport);
const mockedStatus = vi.mocked(api.fetchReportStatus);
const mockedCreate = vi.mocked(api.createOutreachEvent);

const noop = () => {};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("<ImportReplyModal />", () => {
  it("renders nothing when closed", () => {
    const { container } = render(
      <ImportReplyModal open={false} onClose={noop} onArchived={noop} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders textarea when open", () => {
    render(<ImportReplyModal open={true} onClose={noop} onArchived={noop} />);
    expect(screen.getByPlaceholderText(/粘贴对方的邮件正文/)).toBeInTheDocument();
  });

  it("falls back to editable form when parse fails", async () => {
    mockedGenerate.mockRejectedValueOnce(new Error("network error"));

    render(
      <ImportReplyModal open={true} onClose={noop} onArchived={noop} defaultCompany="Pfizer" />,
    );

    const textarea = screen.getByPlaceholderText(/粘贴对方的邮件正文/);
    fireEvent.change(textarea, { target: { value: "some reply content" } });
    fireEvent.click(screen.getByRole("button", { name: "解析" }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("Pfizer")).toBeInTheDocument();
    });

    const archiveBtn = screen.getByRole("button", { name: "归档" });
    expect(archiveBtn).toBeInTheDocument();
  });

  it("calls onArchived after successful archive", async () => {
    mockedGenerate.mockResolvedValueOnce({ task_id: "t1", status: "pending" });
    mockedStatus.mockResolvedValueOnce({
      task_id: "t1",
      status: "done",
      result: {
        meta: {
          to_company: "Roche",
          status: "replied",
          next_step: "schedule call",
          keywords: "ADC",
          notes: "interested",
        },
      },
    });
    mockedCreate.mockResolvedValueOnce({
      id: 99,
      to_company: "Roche",
      to_contact: null,
      purpose: "follow_up",
      channel: "email",
      status: "replied",
      asset_context: null,
      perspective: null,
      subject: null,
      notes: "interested",
      session_id: null,
      created_at: new Date().toISOString(),
    });

    const onArchived = vi.fn();
    const onClose = vi.fn();

    render(<ImportReplyModal open={true} onClose={onClose} onArchived={onArchived} />);

    const textarea = screen.getByPlaceholderText(/粘贴对方的邮件正文/);
    fireEvent.change(textarea, { target: { value: "Roche replied positively" } });
    fireEvent.click(screen.getByRole("button", { name: "解析" }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("Roche")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "归档" }));

    await waitFor(() => {
      expect(onArchived).toHaveBeenCalledOnce();
    });
  });
});

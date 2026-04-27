import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DdTabPage from "../page";
import * as api from "@/lib/api";

const MOCK_ASSET: Partial<api.SellAssetDetail> = {
  id: 42,
  entity_key: "BCMA CAR-T",
  notes: "preclinical, IND in 6 months",
  added_at: "2026-04-01T00:00:00Z",
  outreach_count: 0,
  last_outreach_at: null,
  crm_metadata: null,
  recent_outreach: [],
};

vi.mock("../../layout", () => ({
  useSellAsset: () => ({
    asset: MOCK_ASSET,
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ assetId: "42" }),
}));

const DONE_RESP = {
  task_id: "t1",
  status: "completed",
  result: { markdown: "# result", files: [], meta: {} },
} satisfies api.GenerateReportResponse;

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("DD timeline tab", () => {
  it("renders all three generate buttons", () => {
    render(<DdTabPage />);
    expect(screen.getByRole("button", { name: /生成 DD checklist/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /预生成 FAQ/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /生成 meeting-brief/i })).toBeInTheDocument();
  });

  it("clicking DD checklist button calls generateReport with slug dd-checklist and seller perspective", async () => {
    vi.spyOn(api, "generateReport").mockResolvedValue(DONE_RESP);
    render(<DdTabPage />);
    fireEvent.click(screen.getByRole("button", { name: /生成 DD checklist/i }));
    await waitFor(() => {
      expect(api.generateReport).toHaveBeenCalledWith(
        "dd-checklist",
        expect.objectContaining({ perspective: "seller" }),
      );
    });
  });

  it("clicking FAQ button calls generateReport with slug dd-faq", async () => {
    vi.spyOn(api, "generateReport").mockResolvedValue({ ...DONE_RESP, task_id: "t2" });
    render(<DdTabPage />);
    fireEvent.click(screen.getByRole("button", { name: /预生成 FAQ/i }));
    await waitFor(() => {
      expect(api.generateReport).toHaveBeenCalledWith("dd-faq", expect.any(Object));
    });
  });

  it("clicking meeting-brief button calls generateReport with slug meeting-brief", async () => {
    vi.spyOn(api, "generateReport").mockResolvedValue({ ...DONE_RESP, task_id: "t3" });
    render(<DdTabPage />);
    fireEvent.click(screen.getByRole("button", { name: /生成 meeting-brief/i }));
    await waitFor(() => {
      expect(api.generateReport).toHaveBeenCalledWith("meeting-brief", expect.any(Object));
    });
  });
});

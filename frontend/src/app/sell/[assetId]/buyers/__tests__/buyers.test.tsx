import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import SellAssetLayout from "../../layout";
import BuyersTabPage from "../page";
import * as api from "@/lib/api";

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const MOCK_ASSET: api.SellAssetDetail = {
  id: 42,
  entity_key: "BCMA CAR-T",
  notes: "preclinical",
  added_at: "2026-04-01T00:00:00Z",
  outreach_count: 0,
  last_outreach_at: null,
  crm_metadata: null,
  recent_outreach: [],
};

const MOCK_MARKDOWN = `# BCMA NSCLC — Top 2 买方候选清单

## 排名总览

| 排名 | 买方 | 战略契合度 | 核心理由 |
|------|------|-----------|----------|
| 1 | Roche | ⭐⭐⭐⭐⭐ (5/5) | 核心赛道吻合 |
| 2 | AstraZeneca | ⭐⭐⭐⭐ (4/5) | 互补管线 |
`;

const MOCK_OUTREACH_EVENT: api.OutreachEvent = {
  id: 1,
  to_company: "Roche",
  to_contact: null,
  purpose: "cold_outreach",
  channel: "email",
  status: "draft",
  asset_context: "BCMA CAR-T",
  perspective: null,
  subject: null,
  notes: null,
  session_id: null,
  created_at: "2026-04-27T00:00:00Z",
};

// ─── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  useParams: () => ({ assetId: "42" }),
  usePathname: () => "/sell/42/buyers",
  useRouter: () => ({ push: vi.fn() }),
}));

beforeEach(() => {
  vi.restoreAllMocks();
});

// ─── Helpers ──────────────────────────────────────────────────────────────────

function renderPage() {
  vi.spyOn(api, "fetchSellAsset").mockResolvedValue(MOCK_ASSET);
  return render(
    <SellAssetLayout>
      <BuyersTabPage />
    </SellAssetLayout>,
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("BuyersTabPage — form prefill", () => {
  it("prefills target input with asset.entity_key", async () => {
    renderPage();
    await waitFor(() => {
      const input = screen.getByPlaceholderText("e.g. KRAS G12C") as HTMLInputElement;
      expect(input.value).toBe("BCMA CAR-T");
    });
  });

  it("leaves indication empty by default", async () => {
    renderPage();
    await waitFor(() => screen.getByPlaceholderText("e.g. NSCLC 一线"));
    const input = screen.getByPlaceholderText("e.g. NSCLC 一线") as HTMLInputElement;
    expect(input.value).toBe("");
  });
});

describe("BuyersTabPage — run & render table", () => {
  it("renders buyer table rows after a completed report", async () => {
    vi.spyOn(api, "generateReport").mockResolvedValue({
      task_id: "t1",
      status: "completed",
      result: { markdown: MOCK_MARKDOWN },
    });

    renderPage();
    await waitFor(() => screen.getByText("运行匹配"));

    // fill indication so validation passes
    fireEvent.change(screen.getByPlaceholderText("e.g. NSCLC 一线"), {
      target: { value: "NSCLC 一线" },
    });
    fireEvent.click(screen.getByText("运行匹配"));

    await waitFor(() => {
      expect(screen.getByText("Roche")).toBeInTheDocument();
      expect(screen.getByText("AstraZeneca")).toBeInTheDocument();
    });
    expect(screen.getAllByText("+ 加入 outreach")).toHaveLength(2);
  });

  it("shows validation error when indication is empty", async () => {
    renderPage();
    await waitFor(() => screen.getByText("运行匹配"));
    // target is prefilled; indication is empty
    fireEvent.click(screen.getByText("运行匹配"));
    await waitFor(() => {
      expect(screen.getByText("请填写靶点和适应症")).toBeInTheDocument();
    });
  });
});

describe("BuyersTabPage — outreach action", () => {
  it("calls createOutreachEvent with correct payload when '+ 加入 outreach' is clicked", async () => {
    vi.spyOn(api, "generateReport").mockResolvedValue({
      task_id: "t1",
      status: "completed",
      result: { markdown: MOCK_MARKDOWN },
    });
    vi.spyOn(api, "createOutreachEvent").mockResolvedValue(MOCK_OUTREACH_EVENT);

    renderPage();
    await waitFor(() => screen.getByText("运行匹配"));

    fireEvent.change(screen.getByPlaceholderText("e.g. NSCLC 一线"), {
      target: { value: "NSCLC" },
    });
    fireEvent.click(screen.getByText("运行匹配"));

    await waitFor(() => screen.getAllByText("+ 加入 outreach"));

    const btns = screen.getAllByText("+ 加入 outreach");
    fireEvent.click(btns[0]); // first row = Roche

    await waitFor(() => {
      expect(api.createOutreachEvent).toHaveBeenCalledWith({
        to_company: "Roche",
        status: "draft",
        purpose: "cold_outreach",
        asset_context: "BCMA CAR-T",
      });
    });
  });
});

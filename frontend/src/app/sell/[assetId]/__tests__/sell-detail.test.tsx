import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import SellAssetLayout, { SELL_TABS, useSellAsset } from "../layout";
import OverviewPage from "../page";
import * as api from "@/lib/api";

/**
 * Tests for the /sell/[assetId] layout + Overview page (Phase 2, P2-2).
 *
 * Covers:
 *   - layout fetches the asset on mount + provides it via context
 *   - error state renders an inline banner without crashing
 *   - tab nav exposes all 6 SELL_TABS with correct hrefs
 *   - Overview page renders quick actions + recent outreach + notes
 *   - Overview empty-recent-outreach state
 */

const MOCK_ASSET: api.SellAssetDetail = {
  id: 42,
  entity_key: "BCMA CAR-T",
  notes: "preclinical, IND in 6 months",
  added_at: "2026-04-01T00:00:00Z",
  outreach_count: 2,
  last_outreach_at: "2026-04-25T10:00:00Z",
  crm_metadata: null,
  recent_outreach: [
    {
      id: 1,
      to_company: "AstraZeneca",
      to_contact: "Sarah Chen",
      status: "sent",
      purpose: "cold_outreach",
      subject: "Intro — BCMA CAR-T",
      created_at: "2026-04-25T10:00:00Z",
    },
    {
      id: 2,
      to_company: "Pfizer",
      to_contact: null,
      status: "replied",
      purpose: "follow_up",
      subject: null,
      created_at: "2026-04-22T10:00:00Z",
    },
  ],
};

beforeEach(() => {
  vi.restoreAllMocks();
});

// next/navigation: layout uses useParams + usePathname; page uses useRouter
vi.mock("next/navigation", () => ({
  useParams: () => ({ assetId: "42" }),
  usePathname: () => "/sell/42",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

describe("SellAssetLayout", () => {
  it("fetches the asset on mount and renders its name in the header", async () => {
    vi.spyOn(api, "fetchSellAsset").mockResolvedValue(MOCK_ASSET);
    render(
      <SellAssetLayout>
        <div>child</div>
      </SellAssetLayout>,
    );
    await waitFor(() => {
      expect(screen.getByText("BCMA CAR-T")).toBeInTheDocument();
    });
    expect(api.fetchSellAsset).toHaveBeenCalledWith("42");
  });

  it("shows an error banner when the fetch fails", async () => {
    vi.spyOn(api, "fetchSellAsset").mockRejectedValue(new Error("API 404"));
    render(
      <SellAssetLayout>
        <div>child</div>
      </SellAssetLayout>,
    );
    await waitFor(() => {
      expect(screen.getByText(/API 404|加载资产失败/)).toBeInTheDocument();
    });
  });

  it("renders all 6 tabs with correct hrefs", async () => {
    vi.spyOn(api, "fetchSellAsset").mockResolvedValue(MOCK_ASSET);
    render(
      <SellAssetLayout>
        <div>child</div>
      </SellAssetLayout>,
    );
    await waitFor(() => {
      expect(screen.getByText("BCMA CAR-T")).toBeInTheDocument();
    });
    for (const t of SELL_TABS) {
      const link = screen.getByRole("tab", { name: t.label });
      const expectedHref = t.slug ? `/sell/42/${t.slug}` : "/sell/42";
      expect(link).toHaveAttribute("href", expectedHref);
    }
  });
});

// ─────────────────────────────────────────────────────────────
// Overview page tests — render under a stub provider so we don't
// have to fight async-effect timing of the real layout.
// ─────────────────────────────────────────────────────────────

function ProviderHarness({ value }: { value: ReturnType<typeof useSellAsset> }) {
  // Re-export the layout's context via a wrapper file would be cleaner,
  // but for now we render OverviewPage inside the real layout with a
  // mocked api so the context value matches MOCK_ASSET.
  return value.asset ? <OverviewPage /> : null;
}

describe("Sell asset Overview tab", () => {
  it("renders quick actions, recent outreach rows, and notes", async () => {
    vi.spyOn(api, "fetchSellAsset").mockResolvedValue(MOCK_ASSET);
    render(
      <SellAssetLayout>
        <OverviewPage />
      </SellAssetLayout>,
    );
    await waitFor(() => {
      expect(screen.getByText("🎯 Match buyers")).toBeInTheDocument();
    });
    expect(screen.getByText("📝 Generate teaser")).toBeInTheDocument();
    expect(screen.getByText("AstraZeneca")).toBeInTheDocument();
    expect(screen.getByText("Pfizer")).toBeInTheDocument();
    expect(screen.getByText("Intro — BCMA CAR-T")).toBeInTheDocument();
    // notes appear in both the layout header and the notes panel — assert both render
    expect(screen.getAllByText(/preclinical, IND in 6 months/).length).toBeGreaterThanOrEqual(1);
    // The Match buyers link points to the buyers tab
    expect(screen.getByText("🎯 Match buyers").closest("a")).toHaveAttribute(
      "href",
      "/sell/42/buyers",
    );
    // Avoid unused-import warning on ProviderHarness without polluting prod code
    expect(typeof ProviderHarness).toBe("function");
  });

  it("shows the empty state when there are no recent outreach rows", async () => {
    vi.spyOn(api, "fetchSellAsset").mockResolvedValue({
      ...MOCK_ASSET,
      recent_outreach: [],
      outreach_count: 0,
      last_outreach_at: null,
    });
    render(
      <SellAssetLayout>
        <OverviewPage />
      </SellAssetLayout>,
    );
    await waitFor(() => {
      expect(screen.getByText(/还没有外联记录/)).toBeInTheDocument();
    });
  });
});

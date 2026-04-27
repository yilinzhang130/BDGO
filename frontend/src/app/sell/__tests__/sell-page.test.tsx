import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import SellPage from "../page";
import * as api from "@/lib/api";

/**
 * Smoke tests for the /sell workspace home (Phase 2, P2-1).
 *
 * Covers the three states the page can be in: loading → empty,
 * loading → populated, loading → error. Detail-tab nav and the
 * actual asset detail page get their own tests in PR P2-2.
 */

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("<SellPage />", () => {
  it("renders the empty state when the user has no sell-side assets", async () => {
    vi.spyOn(api, "fetchSellAssets").mockResolvedValue({
      data: [],
      page: 1,
      page_size: 100,
      total: 0,
      total_pages: 1,
    });

    render(<SellPage />);

    await waitFor(() => {
      expect(screen.getByText("还没有卖方资产")).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: /Watchlist/i })).toHaveAttribute("href", "/watchlist");
  });

  it("renders an asset card per row + a link to the detail page", async () => {
    vi.spyOn(api, "fetchSellAssets").mockResolvedValue({
      data: [
        {
          id: 7,
          entity_key: "KRAS G12D NSCLC",
          notes: "preclinical IND-ready",
          added_at: "2026-04-01T00:00:00Z",
          outreach_count: 3,
          last_outreach_at: "2026-04-25T00:00:00Z",
          crm_metadata: null,
        },
      ],
      page: 1,
      page_size: 100,
      total: 1,
      total_pages: 1,
    });

    render(<SellPage />);

    await waitFor(() => {
      expect(screen.getByText("KRAS G12D NSCLC")).toBeInTheDocument();
    });
    expect(screen.getByText("preclinical IND-ready")).toBeInTheDocument();
    expect(screen.getByText(/3 次外联/)).toBeInTheDocument();
    const cardLink = screen.getByText("KRAS G12D NSCLC").closest("a");
    expect(cardLink).toHaveAttribute("href", "/sell/7");
  });

  it("surfaces a backend error in the banner without crashing", async () => {
    vi.spyOn(api, "fetchSellAssets").mockRejectedValue(new Error("API 500"));

    render(<SellPage />);

    await waitFor(() => {
      expect(screen.getByText(/API 500|加载资产失败/)).toBeInTheDocument();
    });
  });
});

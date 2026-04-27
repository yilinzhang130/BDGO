import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SellAssetLayout from "../../layout";
import TeaserTabPage from "../page";
import * as api from "@/lib/api";

const MOCK_ASSET: api.SellAssetDetail = {
  id: 7,
  entity_key: "GLP-1 Agonist",
  notes: "Phase 2 ready",
  added_at: "2026-01-01T00:00:00Z",
  outreach_count: 0,
  last_outreach_at: null,
  crm_metadata: null,
  recent_outreach: [],
};

const MOCK_RESULT = {
  markdown: "# GLP-1 Agonist Teaser\nStrong efficacy data.",
  files: [
    { filename: "teaser.docx", format: "docx", size: 1024, download_url: "/files/teaser.docx" },
    { filename: "teaser.pptx", format: "pptx", size: 2048, download_url: "/files/teaser.pptx" },
  ],
  meta: { title: "GLP-1 Teaser" },
};

// Mock returns status=completed so the page renders results without hitting pollTask
const MOCK_DONE_RESP = { task_id: "task-001", status: "completed", result: MOCK_RESULT };
const MOCK_RUNNING_RESP = { task_id: "task-001", status: "running" };

vi.mock("next/navigation", () => ({
  useParams: () => ({ assetId: "7" }),
  usePathname: () => "/sell/7/teaser",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => ({ get: (_k: string) => null }),
}));

function renderPage() {
  return render(
    <SellAssetLayout>
      <TeaserTabPage />
    </SellAssetLayout>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// ── Form rendering ─────────────────────────────────────────────

describe("TeaserTabPage — form", () => {
  it("renders all form controls and the generate button", async () => {
    vi.spyOn(api, "fetchSellAsset").mockResolvedValue(MOCK_ASSET);
    renderPage();
    await waitFor(() => expect(screen.getByTestId("audience-select")).toBeInTheDocument());
    expect(screen.getByTestId("language-select")).toBeInTheDocument();
    expect(screen.getByText(/单页 One-pager/)).toBeInTheDocument();
    expect(screen.getByText(/双页 Two-pager/)).toBeInTheDocument();
    expect(screen.getByText(/疗效 Efficacy/)).toBeInTheDocument();
    expect(screen.getByText(/安全性 Safety/)).toBeInTheDocument();
    expect(screen.getByTestId("generate-base-btn")).toBeInTheDocument();
    expect(screen.getByTestId("buyer-input")).toBeInTheDocument();
  });

  it("shows idle hint in result panel before generation", async () => {
    vi.spyOn(api, "fetchSellAsset").mockResolvedValue(MOCK_ASSET);
    renderPage();
    await waitFor(() => expect(screen.getByTestId("generate-base-btn")).toBeInTheDocument());
    expect(screen.getByText(/填写左侧参数后点击/)).toBeInTheDocument();
  });
});

// ── Base generation ────────────────────────────────────────────

describe("TeaserTabPage — base generation", () => {
  it("calls generateReport with deal-teaser slug and correct params", async () => {
    vi.spyOn(api, "fetchSellAsset").mockResolvedValue(MOCK_ASSET);
    vi.spyOn(api, "generateReport").mockResolvedValue(MOCK_RUNNING_RESP);

    renderPage();
    await waitFor(() => expect(screen.getByTestId("generate-base-btn")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("generate-base-btn"));

    await waitFor(() =>
      expect(api.generateReport).toHaveBeenCalledWith(
        "deal-teaser",
        expect.objectContaining({
          audience: "MNC",
          language: "zh",
          length: "one-pager",
          asset_context: "GLP-1 Agonist",
        }),
      ),
    );
    // Button text changes to "生成中"
    expect(screen.getByTestId("generate-base-btn")).toHaveTextContent("生成中");
  });

  it("shows markdown preview and download links when generateReport returns completed", async () => {
    vi.spyOn(api, "fetchSellAsset").mockResolvedValue(MOCK_ASSET);
    vi.spyOn(api, "generateReport").mockResolvedValue(MOCK_DONE_RESP);

    renderPage();
    await waitFor(() => expect(screen.getByTestId("generate-base-btn")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("generate-base-btn"));

    await waitFor(() => expect(screen.getByTestId("markdown-preview")).toBeInTheDocument());
    expect(screen.getByTestId("markdown-preview")).toHaveTextContent("GLP-1 Agonist Teaser");
    expect(screen.getByText(/\.docx/)).toBeInTheDocument();
    expect(screen.getByText(/\.pptx/)).toBeInTheDocument();
  });

  it("shows error banner when generateReport throws", async () => {
    vi.spyOn(api, "fetchSellAsset").mockResolvedValue(MOCK_ASSET);
    vi.spyOn(api, "generateReport").mockRejectedValue(new Error("API 500"));

    renderPage();
    await waitFor(() => expect(screen.getByTestId("generate-base-btn")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("generate-base-btn"));

    await waitFor(() => expect(screen.getByText("API 500")).toBeInTheDocument());
  });

  it("passes emphasis checkboxes in params", async () => {
    vi.spyOn(api, "fetchSellAsset").mockResolvedValue(MOCK_ASSET);
    vi.spyOn(api, "generateReport").mockResolvedValue(MOCK_DONE_RESP);

    renderPage();
    await waitFor(() => expect(screen.getByText(/安全性 Safety/)).toBeInTheDocument());

    // Toggle safety checkbox
    const safetyLabel = screen.getByText(/安全性 Safety/);
    const safetyCheckbox = safetyLabel.closest("label")!.querySelector("input")!;
    fireEvent.click(safetyCheckbox);

    fireEvent.click(screen.getByTestId("generate-base-btn"));

    await waitFor(() =>
      expect(api.generateReport).toHaveBeenCalledWith(
        "deal-teaser",
        expect.objectContaining({ emphasis: expect.arrayContaining(["safety"]) }),
      ),
    );
  });
});

// ── Buyer variant generation ───────────────────────────────────

describe("TeaserTabPage — buyer variant generation", () => {
  async function setupWithBaseGenerated() {
    vi.spyOn(api, "fetchSellAsset").mockResolvedValue(MOCK_ASSET);
    vi.spyOn(api, "generateReport").mockResolvedValue(MOCK_DONE_RESP);

    renderPage();
    await waitFor(() => expect(screen.getByTestId("generate-base-btn")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("generate-base-btn"));
    await waitFor(() => expect(screen.getByTestId("markdown-preview")).toBeInTheDocument());
  }

  it("variant button is disabled before base teaser is generated", async () => {
    vi.spyOn(api, "fetchSellAsset").mockResolvedValue(MOCK_ASSET);
    renderPage();
    await waitFor(() => expect(screen.getByTestId("buyer-input")).toBeInTheDocument());

    fireEvent.change(screen.getByTestId("buyer-input"), { target: { value: "Roche" } });

    expect(screen.getByTestId("generate-variant-btn")).toBeDisabled();
  });

  it("generates a buyer variant and passes buyer_hint in params", async () => {
    await setupWithBaseGenerated();

    // Reset mock for variant call
    vi.spyOn(api, "generateReport").mockResolvedValue({
      task_id: "task-002",
      status: "completed",
      result: { ...MOCK_RESULT, markdown: "# AZ variant" },
    });

    fireEvent.change(screen.getByTestId("buyer-input"), {
      target: { value: "AstraZeneca" },
    });
    fireEvent.click(screen.getByTestId("generate-variant-btn"));

    await waitFor(() =>
      expect(api.generateReport).toHaveBeenCalledWith(
        "deal-teaser",
        expect.objectContaining({ buyer_hint: "AstraZeneca" }),
      ),
    );
  });

  it("shows variant card with result after buyer variant completes", async () => {
    await setupWithBaseGenerated();

    vi.spyOn(api, "generateReport").mockResolvedValue({
      task_id: "task-002",
      status: "completed",
      result: { ...MOCK_RESULT, markdown: "# AstraZeneca variant" },
    });

    fireEvent.change(screen.getByTestId("buyer-input"), {
      target: { value: "AstraZeneca" },
    });
    fireEvent.click(screen.getByTestId("generate-variant-btn"));

    await waitFor(() => expect(screen.getByText(/🏢 AstraZeneca/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/AstraZeneca variant/)).toBeInTheDocument());
  });

  it("shows variant error when generateReport throws for buyer", async () => {
    await setupWithBaseGenerated();

    vi.spyOn(api, "generateReport").mockRejectedValue(new Error("Quota exceeded"));

    fireEvent.change(screen.getByTestId("buyer-input"), {
      target: { value: "Novartis" },
    });
    fireEvent.click(screen.getByTestId("generate-variant-btn"));

    await waitFor(() => expect(screen.getByText("Quota exceeded")).toBeInTheDocument());
  });
});

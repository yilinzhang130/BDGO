import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";

/**
 * Hook-level tests for useSlashCommand — specifically the silent-catch
 * fix from #132 that replaced `.catch(() => {})` with retry + error
 * state + visible banner.
 *
 * Two collaborators are mocked at the module boundary:
 *   - @/lib/api fetchReportServices (the call we want to fail/succeed)
 *   - @/lib/sessions useSessionStore (returns minimal store; no real
 *     persistence needed for these tests)
 *
 * Real timers are used (not fake): vitest fake timers + waitFor + React
 * 19 act() race subtly. Total backoff per failing test is bounded at
 * ~3.2s (0 + 800 + 2400 ms), each test sets its own waitFor / it timeout
 * accordingly.
 */

// ── Mocks ──────────────────────────────────────────────────

const mockFetch = vi.fn();
vi.mock("@/lib/api", () => ({
  fetchReportServices: () => mockFetch(),
  // parseReportArgs / generateReport are unused by the tests below — stub
  // them so the import doesn't fail.
  parseReportArgs: vi.fn(),
  generateReport: vi.fn(),
}));

vi.mock("@/lib/sessions", () => ({
  autoTitleFromFirstMessage: vi.fn(),
  useSessionStore: () => ({
    activeId: null,
    addMessage: vi.fn(),
    addReportTask: vi.fn(),
    markMessageDone: vi.fn(),
  }),
}));

// Pull useSlashCommand AFTER the mocks are wired so the import gets the
// patched modules.
import { useSlashCommand } from "../useSlashCommand";

const SAMPLE_SERVICES = [
  {
    slug: "buyer-profile",
    display_name: "MNC Buyer Profile",
    description: "Buyer profile for MNC pharma",
    estimated_seconds: 60,
    output_formats: ["docx", "md"],
    mode: "async",
    category: "report",
  },
  {
    slug: "draft-spa",
    display_name: "Draft SPA / Merger",
    description: "Generate SPA skeleton",
    estimated_seconds: 100,
    output_formats: ["docx", "md"],
    mode: "async",
    category: "report",
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  // Real timers: fake timers + waitFor + React 19 act() race in subtle
  // ways. The retry backoff total is bounded at ~3.2s (0 + 800 + 2400),
  // covered by the per-test 6s timeout below.
});

const noopGetInput = () => "";
const noopSetInput = () => {};

// ── Happy path ─────────────────────────────────────────────

describe("useSlashCommand — services-fetch happy path", () => {
  it("populates reportServices and clears error/loading on success", async () => {
    mockFetch.mockResolvedValueOnce({ services: SAMPLE_SERVICES });

    const { result } = renderHook(() => useSlashCommand(noopGetInput, noopSetInput));

    // Initially loading, no error
    expect(result.current.servicesLoading).toBe(true);
    expect(result.current.servicesLoadError).toBe(null);

    // Run all pending promises (fetch is sync-resolving here)

    await waitFor(() => expect(result.current.servicesLoading).toBe(false));

    expect(result.current.servicesLoadError).toBe(null);
    // displayName comes from the merged service, not the slug fallback
    const buyerProfile = result.current.slashCommandsAll.find((c) => c.slug === "buyer-profile");
    expect(buyerProfile?.displayName).toBe("MNC Buyer Profile");
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });
});

// ── Failure: silent-catch regression guard ────────────────

describe("useSlashCommand — services-fetch failure (#132 regression guard)", () => {
  // Retries take real time: 0ms + 800ms + 2400ms = 3.2s before the
  // 3rd-attempt failure surfaces. Bump waitFor timeout above that.
  const RETRY_TIMEOUT_MS = 5000;

  it(
    "retries 3 times then exposes the error (no silent swallow)",
    async () => {
      const err = new TypeError("NetworkError");
      mockFetch.mockRejectedValue(err);

      const { result } = renderHook(() => useSlashCommand(noopGetInput, noopSetInput));

      expect(result.current.servicesLoading).toBe(true);

      await waitFor(() => expect(result.current.servicesLoading).toBe(false), {
        timeout: RETRY_TIMEOUT_MS,
      });

      expect(mockFetch).toHaveBeenCalledTimes(3);
      expect(result.current.servicesLoadError).toBe("NetworkError");
      // Slash list still renders (from static SLASH_COMMANDS) but with
      // displayName fallback to slug
      const buyerProfile = result.current.slashCommandsAll.find((c) => c.slug === "buyer-profile");
      expect(buyerProfile?.displayName).toBe("buyer-profile"); // slug fallback
      expect(buyerProfile?.description).toBe("");
    },
    RETRY_TIMEOUT_MS + 1000,
  );

  it(
    "recovers when an early attempt fails but a later one succeeds",
    async () => {
      mockFetch
        .mockRejectedValueOnce(new Error("transient 1"))
        .mockRejectedValueOnce(new Error("transient 2"))
        .mockResolvedValueOnce({ services: SAMPLE_SERVICES });

      const { result } = renderHook(() => useSlashCommand(noopGetInput, noopSetInput));

      await waitFor(() => expect(result.current.servicesLoading).toBe(false), {
        timeout: RETRY_TIMEOUT_MS,
      });

      expect(mockFetch).toHaveBeenCalledTimes(3);
      expect(result.current.servicesLoadError).toBe(null);
      const draftSpa = result.current.slashCommandsAll.find((c) => c.slug === "draft-spa");
      expect(draftSpa?.displayName).toBe("Draft SPA / Merger");
    },
    RETRY_TIMEOUT_MS + 1000,
  );

  it(
    "retryLoadServices() refetches and clears prior error",
    async () => {
      // First load fails everything
      mockFetch.mockRejectedValue(new Error("down"));

      const { result } = renderHook(() => useSlashCommand(noopGetInput, noopSetInput));

      await waitFor(() => expect(result.current.servicesLoadError).toBe("down"), {
        timeout: RETRY_TIMEOUT_MS,
      });
      expect(mockFetch).toHaveBeenCalledTimes(3);

      // Now backend recovers; user clicks retry
      mockFetch.mockReset();
      mockFetch.mockResolvedValueOnce({ services: SAMPLE_SERVICES });

      await act(async () => {
        await result.current.retryLoadServices();
      });

      expect(mockFetch).toHaveBeenCalledTimes(1); // single fresh attempt
      expect(result.current.servicesLoadError).toBe(null);
      expect(result.current.servicesLoading).toBe(false);
    },
    RETRY_TIMEOUT_MS + 2000,
  );
});

// ── Empty-list edge case ─────────────────────────────────

describe("useSlashCommand — empty services response", () => {
  it("treats empty services array as success (not retried) but warns", async () => {
    mockFetch.mockResolvedValueOnce({ services: [] });
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    const { result } = renderHook(() => useSlashCommand(noopGetInput, noopSetInput));

    await waitFor(() => expect(result.current.servicesLoading).toBe(false));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(result.current.servicesLoadError).toBe(null);
    // Console warn fired — server-side misconfig signalled to devtools
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining("returned 0 services"));

    warnSpy.mockRestore();
  });
});

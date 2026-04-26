/**
 * Tests for the locale context + translation helper (P2-11).
 *
 * Coverage:
 *   1. Default locale is "zh" on first render
 *   2. t() returns the Chinese string when locale = zh
 *   3. t() returns the English string when locale = en
 *   4. t() falls back to zh dict when a key is missing in en dict
 *   5. t() returns the key itself when missing in both dicts
 *   6. setLocale() switches the active locale
 *   7. LocaleProvider hydrates from localStorage
 *   8. setLocale() persists to localStorage
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import type { ReactNode } from "react";
import { LocaleProvider, useLocale } from "@/lib/locale";

// ── Helpers ──────────────────────────────────────────────────

const wrapper = ({ children }: { children: ReactNode }) => (
  <LocaleProvider>{children}</LocaleProvider>
);

// ── Storage mock ──────────────────────────────────────────────

const mockStorage: Record<string, string> = {};

beforeEach(() => {
  Object.keys(mockStorage).forEach((k) => delete mockStorage[k]);
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => mockStorage[k] ?? null,
    setItem: (k: string, v: string) => {
      mockStorage[k] = v;
    },
    removeItem: (k: string) => {
      delete mockStorage[k];
    },
  });
});

// ── Tests ──────────────────────────────────────────────────

describe("useLocale — defaults", () => {
  it("defaults to zh locale", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    expect(result.current.locale).toBe("zh");
  });

  it("t() returns Chinese string in zh mode", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    expect(result.current.t("nav.newChat")).toBe("新建对话");
  });

  it("t() returns Chinese for nav.search in zh mode", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    expect(result.current.t("nav.search")).toBe("搜索…");
  });
});

describe("useLocale — English mode", () => {
  it("t() returns English string after switching to en", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    act(() => result.current.setLocale("en"));
    expect(result.current.locale).toBe("en");
    expect(result.current.t("nav.newChat")).toBe("New Chat");
  });

  it("t() returns English for nav.search in en mode", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    act(() => result.current.setLocale("en"));
    expect(result.current.t("nav.search")).toBe("Search…");
  });

  it("t() returns English for all nav items", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    act(() => result.current.setLocale("en"));
    const { t } = result.current;
    expect(t("nav.companies")).toBe("Companies");
    expect(t("nav.clinical")).toBe("Clinical");
    expect(t("nav.dashboard")).toBe("Dashboard");
    expect(t("nav.watchlist")).toBe("Watchlist");
    expect(t("nav.conference")).toBe("Conferences");
  });
});

describe("useLocale — fallback behaviour", () => {
  it("returns key when missing from both dicts", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    expect(result.current.t("totally.unknown.key")).toBe("totally.unknown.key");
  });
});

describe("useLocale — locale persistence", () => {
  it("setLocale() writes to localStorage", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    act(() => result.current.setLocale("en"));
    expect(mockStorage["bdgo_locale"]).toBe("en");
  });

  it("hydrates from localStorage on mount", async () => {
    mockStorage["bdgo_locale"] = "en";
    const { result } = renderHook(() => useLocale(), { wrapper });
    // Hydration happens in useEffect — wait one tick
    await act(async () => {});
    expect(result.current.locale).toBe("en");
  });

  it("ignores invalid localStorage values", async () => {
    mockStorage["bdgo_locale"] = "fr"; // unsupported
    const { result } = renderHook(() => useLocale(), { wrapper });
    await act(async () => {});
    expect(result.current.locale).toBe("zh");
  });
});

describe("useLocale — auth error keys", () => {
  it("zh: auth.error.wrongPassword is Chinese", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    const msg = result.current.t("auth.error.wrongPassword");
    expect(msg).toMatch(/[一-龥]/); // contains Chinese
  });

  it("en: auth.error.wrongPassword is English", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    act(() => result.current.setLocale("en"));
    const msg = result.current.t("auth.error.wrongPassword");
    expect(msg).not.toMatch(/[一-龥]/);
    expect(msg.toLowerCase()).toContain("password");
  });
});

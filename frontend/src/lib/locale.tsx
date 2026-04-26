"use client";

/**
 * Lightweight i18n — English / Chinese toggle.
 *
 * No URL routing changes needed. Locale is stored in localStorage and
 * provided via React context. Every component calls `useLocale()` and
 * uses the returned `t(key)` translator.
 *
 * Usage:
 *   const { locale, setLocale, t } = useLocale();
 *   t("nav.newChat")  // "New Chat" | "新建对话"
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { en } from "@/locales/en";
import { zh } from "@/locales/zh";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

export type Locale = "zh" | "en";

interface LocaleContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
}

// ─────────────────────────────────────────────────────────────
// Context
// ─────────────────────────────────────────────────────────────

const STORAGE_KEY = "bdgo_locale";

const DICTS: Record<Locale, Record<string, string>> = { zh, en };

const LocaleContext = createContext<LocaleContextValue>({
  locale: "zh",
  setLocale: () => {},
  t: (k) => k,
});

// ─────────────────────────────────────────────────────────────
// Provider
// ─────────────────────────────────────────────────────────────

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("zh");

  // Hydrate from localStorage once on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "en" || stored === "zh") setLocaleState(stored);
    } catch {}
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {}
  }, []);

  const t = useCallback(
    (key: string): string => DICTS[locale][key] ?? DICTS["zh"][key] ?? key,
    [locale],
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

// ─────────────────────────────────────────────────────────────
// Hook
// ─────────────────────────────────────────────────────────────

export function useLocale(): LocaleContextValue {
  return useContext(LocaleContext);
}

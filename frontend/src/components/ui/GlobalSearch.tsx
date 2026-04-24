"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { globalSearch } from "@/lib/api";

const CATEGORY_LABELS: Record<string, string> = {
  companies: "Companies",
  assets: "Assets",
  clinical: "Clinical Trials",
  deals: "Deals",
  ip: "IP / Patents",
};

const CATEGORY_ORDER = ["companies", "assets", "clinical", "deals", "ip"];

interface SearchItem {
  display: Record<string, unknown>;
  link: string;
}
type CategorizedResults = Record<string, SearchItem[]>;

export function GlobalSearch() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<CategorizedResults | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const doSearch = useCallback(async (query: string) => {
    if (query.length < 1) {
      setResults(null);
      setOpen(false);
      return;
    }
    setLoading(true);
    try {
      const data = await globalSearch(query);
      setResults(data.results as unknown as CategorizedResults);
      setOpen(true);
    } catch {
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleInput = (val: string) => {
    setQ(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(val), 300);
  };

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const navigate = (link: string) => {
    setOpen(false);
    setQ("");
    router.push(link);
  };

  const hasResults = results && Object.keys(results).length > 0;

  return (
    <div ref={wrapperRef} className="global-search">
      <input
        value={q}
        onChange={(e) => handleInput(e.target.value)}
        onFocus={() => {
          if (hasResults) setOpen(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            setOpen(false);
            setQ("");
          }
        }}
        placeholder="Search companies, assets, trials, deals, IP..."
        className="global-search-input"
      />
      {loading && <span className="global-search-spinner" />}

      {open && hasResults && (
        <div className="global-search-dropdown">
          {CATEGORY_ORDER.map((cat) => {
            const items = results[cat];
            if (!items || items.length === 0) return null;
            return (
              <div key={cat}>
                <div className="search-category">{CATEGORY_LABELS[cat]}</div>
                {items.map((item, i) => {
                  const display = item.display;
                  const cols = Object.values(display).filter(Boolean);
                  return (
                    <div key={i} className="search-result" onClick={() => navigate(item.link)}>
                      <span className="search-result-primary">{String(cols[0])}</span>
                      {cols.length > 1 && (
                        <span className="search-result-secondary">
                          {cols.slice(1).map(String).join(" · ")}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}

      {open && q && !hasResults && !loading && (
        <div className="global-search-dropdown">
          <div
            style={{
              padding: "1rem",
              color: "var(--text-secondary)",
              fontSize: "0.85rem",
              textAlign: "center",
            }}
          >
            No results for &quot;{q}&quot;
          </div>
        </div>
      )}
    </div>
  );
}

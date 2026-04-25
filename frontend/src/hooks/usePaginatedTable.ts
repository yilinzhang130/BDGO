/**
 * usePaginatedTable — shared pagination + sort + filter logic for client-side
 * CRM data tables (DealsClient, IPClient, etc.).
 *
 * Extracted from DealsClient / IPClient which had identical boilerplate:
 *   useCallback(load) + handleSort + handleFilter + handlePage + searchDebounce.
 *
 * Usage:
 *   const { data, sort, order, handleSort, handleFilter, handlePage } =
 *     usePaginatedTable({ fetchFn: fetchDeals, initialData, defaultSort: "宣布日期", defaultOrder: "desc" });
 */

import { useState, useCallback, useRef } from "react";
import type { PaginatedCRM } from "@/lib/api";

interface Options {
  /** Server-side fetch function — same signature as fetchDeals / fetchIP etc. */
  fetchFn: (params: Record<string, string | number>) => Promise<PaginatedCRM>;
  initialData: PaginatedCRM;
  defaultSort: string;
  defaultOrder: "asc" | "desc";
  /** Initial filter values, e.g. { type: "", status: "" } */
  defaultFilters?: Record<string, string>;
  /** Debounce delay for the "q" (search) filter in ms. Default 300. */
  searchDebounceMs?: number;
}

export function usePaginatedTable({
  fetchFn,
  initialData,
  defaultSort,
  defaultOrder,
  defaultFilters = {},
  searchDebounceMs = 300,
}: Options) {
  const [data, setData] = useState<PaginatedCRM>(initialData);
  const [sort, setSort] = useState(defaultSort);
  const [order, setOrder] = useState<"asc" | "desc">(defaultOrder);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<Record<string, string>>(defaultFilters);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // load() reads the latest state values via closure; callers pass `overrides`
  // for values they've already updated locally (avoids stale-closure issues).
  const load = useCallback(
    (overrides: Record<string, string | number> = {}) => {
      const params: Record<string, string | number> = {
        ...filters,
        sort,
        order,
        page,
        page_size: 50,
        ...overrides,
      };
      fetchFn(params).then(setData);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fetchFn, sort, order, page, filters],
  );

  const handleSort = (col: string) => {
    const newOrder: "asc" | "desc" = sort === col && order === "asc" ? "desc" : "asc";
    setSort(col);
    setOrder(newOrder);
    setPage(1);
    load({ sort: col, order: newOrder, page: 1 });
  };

  /**
   * Update a single filter key and re-fetch.
   * For the "q" (search text) key a 300ms debounce is applied automatically.
   */
  const handleFilter = (key: string, val: string) => {
    const newFilters = { ...filters, [key]: val };
    setFilters(newFilters);

    if (key === "q") {
      // Debounce free-text search to avoid a request per keystroke.
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        setPage(1);
        load({ ...newFilters, page: 1 });
      }, searchDebounceMs);
    } else {
      setPage(1);
      load({ ...newFilters, page: 1 });
    }
  };

  const handlePage = (pg: number) => {
    setPage(pg);
    load({ page: pg });
  };

  return {
    data,
    sort,
    order,
    page,
    filters,
    handleSort,
    handleFilter,
    handlePage,
  };
}

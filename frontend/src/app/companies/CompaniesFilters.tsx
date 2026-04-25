"use client";

import { useRouter } from "next/navigation";
import { useRef } from "react";

interface Props {
  params: Record<string, string>;
}

export function CompaniesFilters({ params }: Props) {
  const router = useRouter();
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  function push(updates: Record<string, string>) {
    const sp = new URLSearchParams(params);
    Object.entries(updates).forEach(([k, v]) => {
      if (v) sp.set(k, v);
      else sp.delete(k);
    });
    sp.delete("page");
    router.push(`?${sp.toString()}`, { scroll: false });
  }

  function onSearch(val: string) {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => push({ q: val }), 300);
  }

  return (
    <div className="filter-bar">
      <input
        placeholder="Search company..."
        defaultValue={params.q ?? ""}
        onChange={(e) => onSearch(e.target.value)}
        style={{ width: 220 }}
      />
      <select
        defaultValue={params.country ?? ""}
        onChange={(e) => push({ country: e.target.value })}
      >
        <option value="">All Countries</option>
        {[
          "USA",
          "China",
          "Korea",
          "UK",
          "France",
          "Germany",
          "Japan",
          "Switzerland",
          "Canada",
          "Israel",
        ].map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
      <select defaultValue={params.type ?? ""} onChange={(e) => push({ type: e.target.value })}>
        <option value="">All Types</option>
        {[
          "Biotech(USA)",
          "Biotech(China)",
          "Biotech(Europe)",
          "Biotech(Other)",
          "海外药企",
          "中国药企",
        ].map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
      <select
        defaultValue={params.priority ?? ""}
        onChange={(e) => push({ priority: e.target.value })}
      >
        <option value="">All Priorities</option>
        {["A", "B", "C", "D"].map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>
      <select
        defaultValue={params.tracked ?? "追踪中"}
        onChange={(e) => push({ tracked: e.target.value })}
      >
        <option value="">All Status</option>
        {["追踪中", "待分类", "排除"].map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </div>
  );
}

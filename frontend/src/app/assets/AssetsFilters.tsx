"use client";

import { useRouter } from "next/navigation";
import { useRef } from "react";

interface Props {
  params: Record<string, string>;
}

export function AssetsFilters({ params }: Props) {
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
        placeholder="Search asset / company..."
        defaultValue={params.q ?? ""}
        onChange={(e) => onSearch(e.target.value)}
        style={{ width: 240 }}
      />
      <select defaultValue={params.phase ?? ""} onChange={(e) => push({ phase: e.target.value })}>
        <option value="">All Phases</option>
        {["Preclinical", "Phase 1", "Phase 2", "Phase 3", "Approved"].map((p) => (
          <option key={p} value={p}>{p}</option>
        ))}
      </select>
      <select defaultValue={params.disease ?? ""} onChange={(e) => push({ disease: e.target.value })}>
        <option value="">All Diseases</option>
        {["Oncology", "Immunology", "Neurology", "Rare Disease", "Cardiology", "Infectious Disease"].map((d) => (
          <option key={d} value={d}>{d}</option>
        ))}
      </select>
      <select defaultValue={params.tracked ?? "追踪中"} onChange={(e) => push({ tracked: e.target.value })}>
        <option value="">All Status</option>
        {["追踪中", "待分类", "排除"].map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
    </div>
  );
}

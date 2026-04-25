"use client";

import { useRouter } from "next/navigation";
import { useRef } from "react";

interface Props {
  params: Record<string, string>;
}

export function ClinicalFilters({ params }: Props) {
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
        placeholder="Search trial / company / asset..."
        defaultValue={params.q ?? ""}
        onChange={(e) => onSearch(e.target.value)}
        style={{ width: 260 }}
      />
      <select defaultValue={params.phase ?? ""} onChange={(e) => push({ phase: e.target.value })}>
        <option value="">All Phases</option>
        {["Phase 1", "Phase 2", "Phase 3", "Phase 1/2", "Phase 2/3"].map((p) => (
          <option key={p} value={p}>{p}</option>
        ))}
      </select>
      <select defaultValue={params.status ?? ""} onChange={(e) => push({ status: e.target.value })}>
        <option value="">All Status</option>
        {["已读出", "待读出", "进行中"].map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
      <select defaultValue={params.result ?? ""} onChange={(e) => push({ result: e.target.value })}>
        <option value="">All Results</option>
        {["阳性", "混合", "阴性", "未达终点"].map((r) => (
          <option key={r} value={r}>{r}</option>
        ))}
      </select>
    </div>
  );
}

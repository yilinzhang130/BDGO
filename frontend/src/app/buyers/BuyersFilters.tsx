"use client";

import { useRouter } from "next/navigation";
import { useRef } from "react";

interface Props {
  params: Record<string, string>;
}

export function BuyersFilters({ params }: Props) {
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
        placeholder="Search buyer company..."
        defaultValue={params.q ?? ""}
        onChange={(e) => onSearch(e.target.value)}
        style={{ width: 260 }}
      />
    </div>
  );
}

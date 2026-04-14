"use client";

import { useState, useEffect } from "react";
import { checkWatchlist, addToWatchlist, removeFromWatchlist } from "@/lib/api";

interface Props {
  entityType: string;
  entityKey: string;
  size?: number;
}

export function WatchlistButton({ entityType, entityKey, size = 20 }: Props) {
  const [watched, setWatched] = useState(false);
  const [itemId, setItemId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    checkWatchlist(entityType, entityKey)
      .then((res) => {
        if (cancelled) return;
        setWatched(res.watched);
        setItemId(res.id ?? null);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [entityType, entityKey]);

  const toggle = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (loading) return;

    // Optimistic update
    const prev = { watched, itemId };
    setWatched(!watched);

    try {
      if (prev.watched && prev.itemId != null) {
        await removeFromWatchlist(prev.itemId);
        setItemId(null);
      } else {
        const res = await addToWatchlist({ entity_type: entityType, entity_key: entityKey });
        setItemId(res.id);
      }
    } catch {
      // Revert on failure
      setWatched(prev.watched);
      setItemId(prev.itemId);
    }
  };

  if (loading) return null;

  return (
    <button
      onClick={toggle}
      title={watched ? "取消关注" : "加入关注"}
      style={{
        background: watched ? "#FEF3C7" : "#F8FAFF",
        border: `1px solid ${watched ? "#FCD34D" : "#E2E8F0"}`,
        borderRadius: 8,
        cursor: "pointer",
        fontSize: size - 4,
        lineHeight: 1,
        color: watched ? "#D97706" : "#94A3B8",
        transition: "all 0.15s",
        padding: "5px 10px",
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        fontWeight: 500,
        fontFamily: "inherit",
        whiteSpace: "nowrap" as const,
      }}
    >
      <span style={{ fontSize: size - 2 }}>{watched ? "\u2605" : "\u2606"}</span>
      <span style={{ fontSize: 12 }}>{watched ? "已关注" : "关注"}</span>
    </button>
  );
}

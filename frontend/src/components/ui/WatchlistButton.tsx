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
      title={watched ? "Remove from watchlist" : "Add to watchlist"}
      style={{
        background: "none",
        border: "none",
        cursor: "pointer",
        fontSize: size,
        lineHeight: 1,
        color: watched ? "#f59e0b" : "#d1d5db",
        transition: "color 0.15s",
        padding: 2,
      }}
    >
      {watched ? "\u2605" : "\u2606"}
    </button>
  );
}

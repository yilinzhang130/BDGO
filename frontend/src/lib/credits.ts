"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchCreditBalance, fetchModels, type CreditBalance, type ModelInfo } from "@/lib/api";

// ═══════════════════════════════════════════
// Credits hook
// ═══════════════════════════════════════════
// Minimal shared store: all consumers subscribe to a single balance value.
// When chatPage finishes a turn it calls refreshCredits() which re-fetches and
// broadcasts to every subscriber (sidebar badge, model picker tooltip, etc).

type Listener = (b: CreditBalance | null) => void;
const listeners = new Set<Listener>();
let current: CreditBalance | null = null;
let inflight: Promise<void> | null = null;

export async function refreshCredits(): Promise<void> {
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      const b = await fetchCreditBalance();
      current = b;
      listeners.forEach((l) => l(b));
    } catch {
      // Leave current as-is on failure; don't flap the UI
    } finally {
      inflight = null;
    }
  })();
  return inflight;
}

/**
 * Optimistic local update — called from the chat stream's `usage` event so
 * the sidebar badge drops immediately without waiting for a network round-trip.
 * The next refreshCredits() reconciles with the server.
 */
export function applyCreditsUsage(creditsCharged: number, serverBalance?: number | null) {
  if (typeof serverBalance === "number") {
    current = current
      ? { ...current, balance: serverBalance }
      : {
          balance: serverBalance,
          total_granted: serverBalance,
          total_spent: 0,
          updated_at: null,
        };
  } else if (current) {
    current = { ...current, balance: Math.max(0, current.balance - creditsCharged) };
  }
  listeners.forEach((l) => l(current));
}

export function useCredits(): {
  balance: CreditBalance | null;
  refresh: () => void;
} {
  const [state, setState] = useState<CreditBalance | null>(current);

  useEffect(() => {
    const listener: Listener = (b) => setState(b);
    listeners.add(listener);
    if (!current) void refreshCredits();
    else setState(current);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  return { balance: state, refresh: refreshCredits };
}

// ═══════════════════════════════════════════
// Models hook (for the picker)
// ═══════════════════════════════════════════

let modelsCache: ModelInfo[] | null = null;

export function useModels(): ModelInfo[] {
  const [models, setModels] = useState<ModelInfo[]>(modelsCache ?? []);

  useEffect(() => {
    if (modelsCache) return;
    fetchModels()
      .then((r) => {
        modelsCache = r.models;
        setModels(r.models);
      })
      .catch(() => {
        // Fall back to an empty list — picker just hides
      });
  }, []);

  return models;
}

// Persist user's selected model across reloads
const MODEL_KEY = "bdgo.selectedModel";

export function getSelectedModel(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(MODEL_KEY) || "";
}

export function setSelectedModel(id: string): void {
  if (typeof window === "undefined") return;
  if (id) window.localStorage.setItem(MODEL_KEY, id);
  else window.localStorage.removeItem(MODEL_KEY);
}

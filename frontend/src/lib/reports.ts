"use client";

import { useSyncExternalStore } from "react";

// ═══════════════════════════════════════════
// Types
// ═══════════════════════════════════════════

export interface ReportFile {
  filename: string;
  format: string;
  size: number;
  download_url: string;
}

export interface CompletedReport {
  taskId: string;
  slug: string;
  displayName: string;
  title: string; // derived from meta or params
  markdownPreview: string;
  files: ReportFile[];
  meta: Record<string, any>;
  createdAt: number;
}

// ═══════════════════════════════════════════
// Store
// ═══════════════════════════════════════════

const STORAGE_KEY = "bdgo.reports.v1";
const MAX_REPORTS = 100;

let state: CompletedReport[] = [];
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function isBrowser() {
  return typeof window !== "undefined" && typeof localStorage !== "undefined";
}

function load(): CompletedReport[] {
  if (!isBrowser()) return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function persist() {
  if (!isBrowser()) return;
  try {
    const trimmed = [...state]
      .sort((a, b) => b.createdAt - a.createdAt)
      .slice(0, MAX_REPORTS);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch (e) {
    console.warn("Reports persist failed:", e);
  }
}

function setState(next: CompletedReport[]) {
  state = next;
  persist();
  emit();
}

if (isBrowser()) {
  state = load();
  window.addEventListener("storage", (e) => {
    if (e.key === STORAGE_KEY) {
      state = load();
      emit();
    }
  });
}

// ═══════════════════════════════════════════
// Public API
// ═══════════════════════════════════════════

export function addCompletedReport(report: CompletedReport) {
  // Dedup by taskId
  const filtered = state.filter((r) => r.taskId !== report.taskId);
  setState([report, ...filtered]);
}

export function removeCompletedReport(taskId: string) {
  setState(state.filter((r) => r.taskId !== taskId));
}

export function clearAllReports() {
  setState([]);
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

function getSnapshot(): CompletedReport[] {
  return state;
}

function getServerSnapshot(): CompletedReport[] {
  return [];
}

export function useReportsStore() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  return {
    reports: [...snapshot].sort((a, b) => b.createdAt - a.createdAt),
    addCompletedReport,
    removeCompletedReport,
    clearAllReports,
  };
}

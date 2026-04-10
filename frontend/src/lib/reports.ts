"use client";

import { useSyncExternalStore } from "react";
import { fetchReportsHistory, deleteReportHistory } from "./api";

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
// Store (server-backed with local cache)
// ═══════════════════════════════════════════

let state: CompletedReport[] = [];
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function isBrowser() {
  return typeof window !== "undefined" && typeof localStorage !== "undefined";
}

function setLocalState(next: CompletedReport[]) {
  state = next;
  emit();
}

// Fire-and-forget helper
function bg(promise: Promise<any>, label: string) {
  promise.catch((err) => console.error(`[reports] ${label}:`, err));
}

// ═══════════════════════════════════════════
// Server hydration
// ═══════════════════════════════════════════

function mapServerReport(raw: any): CompletedReport {
  const files: ReportFile[] = raw.files_json
    ? (typeof raw.files_json === "string" ? JSON.parse(raw.files_json) : raw.files_json)
    : [];
  const meta: Record<string, any> = raw.meta_json
    ? (typeof raw.meta_json === "string" ? JSON.parse(raw.meta_json) : raw.meta_json)
    : {};
  return {
    taskId: raw.task_id || raw.id,
    slug: raw.slug || "",
    displayName: raw.title || raw.slug || "",
    title: raw.title || "",
    markdownPreview: raw.markdown_preview || "",
    files,
    meta,
    createdAt: new Date(raw.created_at).getTime(),
  };
}

async function hydrateFromServer() {
  try {
    const list = await fetchReportsHistory();
    const reports = list.map(mapServerReport);
    setLocalState(reports);
  } catch (err) {
    console.error("[reports] hydrate failed:", err);
  }
}

async function refetch() {
  try {
    const list = await fetchReportsHistory();
    setLocalState(list.map(mapServerReport));
  } catch (err) {
    console.error("[reports] refetch failed:", err);
  }
}

if (isBrowser()) {
  hydrateFromServer();
}

// ═══════════════════════════════════════════
// Public API
// ═══════════════════════════════════════════

export function addCompletedReport(_report: CompletedReport) {
  // The backend auto-saves on report completion, so just refetch
  bg(refetch(), "addCompletedReport");
}

export function removeCompletedReport(taskId: string) {
  // Optimistic: remove locally
  setLocalState(state.filter((r) => r.taskId !== taskId));
  // Find the server-side ID — the taskId is used as lookup
  bg(deleteReportHistory(taskId), "removeCompletedReport");
}

export function clearAllReports() {
  const ids = state.map((r) => r.taskId);
  // Optimistic: clear locally
  setLocalState([]);
  // Delete each on server
  for (const id of ids) {
    bg(deleteReportHistory(id), "clearAllReports");
  }
}

// ═══════════════════════════════════════════
// React hook
// ═══════════════════════════════════════════

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

function getSnapshot(): CompletedReport[] {
  return state;
}

const _serverSnapshot: CompletedReport[] = [];
function getServerSnapshot(): CompletedReport[] {
  return _serverSnapshot;
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

"use client";

import { useSyncExternalStore } from "react";

// ═══════════════════════════════════════════
// Types
// ═══════════════════════════════════════════

export type Role = "user" | "assistant";

export interface ToolEvent {
  type: "tool_call" | "tool_result";
  name: string;
}

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  tools?: ToolEvent[];
  attachments?: string[];
  streaming?: boolean;
  createdAt: number;
}

export type EntityType =
  | "company"
  | "asset"
  | "clinical"
  | "deal"
  | "patent"
  | "buyer";

export interface ContextEntity {
  id: string; // dedupe key: `${entity_type}:${slug}`
  entityType: EntityType;
  title: string;
  subtitle?: string;
  fields: { label: string; value: string }[];
  href?: string;
  addedAt: number;
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
  contextEntities: ContextEntity[];
}

// ═══════════════════════════════════════════
// Store (module-level, localStorage-backed)
// ═══════════════════════════════════════════

const STORAGE_KEY = "bdgo.sessions.v1";
const ACTIVE_KEY = "bdgo.sessions.active";
const MAX_SESSIONS = 50;
const MAX_MESSAGES_PER_SESSION = 200;

interface StoreState {
  sessions: ChatSession[];
  activeId: string | null;
}

let state: StoreState = { sessions: [], activeId: null };
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function isBrowser() {
  return typeof window !== "undefined" && typeof localStorage !== "undefined";
}

function load(): StoreState {
  if (!isBrowser()) return { sessions: [], activeId: null };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const sessions: ChatSession[] = raw ? JSON.parse(raw) : [];
    const activeId = localStorage.getItem(ACTIVE_KEY);
    return { sessions, activeId };
  } catch {
    return { sessions: [], activeId: null };
  }
}

function persist() {
  if (!isBrowser()) return;
  try {
    // Cap messages per session before persisting
    const trimmed = state.sessions.map((s) => ({
      ...s,
      messages: s.messages.slice(-MAX_MESSAGES_PER_SESSION),
    }));
    // Cap total sessions by updatedAt
    const sorted = [...trimmed].sort((a, b) => b.updatedAt - a.updatedAt);
    const capped = sorted.slice(0, MAX_SESSIONS);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(capped));
    if (state.activeId) {
      localStorage.setItem(ACTIVE_KEY, state.activeId);
    } else {
      localStorage.removeItem(ACTIVE_KEY);
    }
  } catch (e) {
    // Quota exceeded — drop oldest sessions and retry
    console.warn("Session persist failed, trimming:", e);
    state.sessions = state.sessions.slice(-20);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.sessions));
    } catch { /* give up */ }
  }
}

function setState(next: StoreState) {
  state = next;
  persist();
  emit();
}

// Initial load (in browser only)
if (isBrowser()) {
  state = load();
  // Cross-tab sync via storage event
  window.addEventListener("storage", (e) => {
    if (e.key === STORAGE_KEY || e.key === ACTIVE_KEY) {
      state = load();
      emit();
    }
  });
}

// ═══════════════════════════════════════════
// Public API
// ═══════════════════════════════════════════

function genId(): string {
  return (
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID().slice(0, 12)
      : Math.random().toString(36).slice(2, 14)
  );
}

export function listSessions(): ChatSession[] {
  return [...state.sessions].sort((a, b) => b.updatedAt - a.updatedAt);
}

export function getSession(id: string): ChatSession | undefined {
  return state.sessions.find((s) => s.id === id);
}

export function getActiveId(): string | null {
  return state.activeId;
}

export function setActiveId(id: string | null) {
  setState({ ...state, activeId: id });
}

export function createSession(title = "New Chat"): ChatSession {
  const now = Date.now();
  const session: ChatSession = {
    id: genId(),
    title,
    createdAt: now,
    updatedAt: now,
    messages: [],
    contextEntities: [],
  };
  setState({
    sessions: [session, ...state.sessions],
    activeId: session.id,
  });
  return session;
}

export function deleteSession(id: string) {
  const remaining = state.sessions.filter((s) => s.id !== id);
  let nextActive = state.activeId;
  if (state.activeId === id) {
    nextActive = remaining.length > 0
      ? [...remaining].sort((a, b) => b.updatedAt - a.updatedAt)[0].id
      : null;
  }
  setState({ sessions: remaining, activeId: nextActive });
}

export function renameSession(id: string, title: string) {
  setState({
    ...state,
    sessions: state.sessions.map((s) =>
      s.id === id ? { ...s, title: title.trim() || "New Chat", updatedAt: Date.now() } : s,
    ),
  });
}

function touchSession(id: string, mutator: (s: ChatSession) => ChatSession) {
  setState({
    ...state,
    sessions: state.sessions.map((s) =>
      s.id === id ? { ...mutator(s), updatedAt: Date.now() } : s,
    ),
  });
}

export function addMessage(sessionId: string, msg: ChatMessage) {
  touchSession(sessionId, (s) => ({
    ...s,
    messages: [...s.messages, msg],
  }));
}

export function appendAssistantChunk(
  sessionId: string,
  msgId: string,
  chunk: string,
) {
  touchSession(sessionId, (s) => ({
    ...s,
    messages: s.messages.map((m) =>
      m.id === msgId ? { ...m, content: m.content + chunk } : m,
    ),
  }));
}

export function addToolEvent(
  sessionId: string,
  msgId: string,
  event: ToolEvent,
) {
  touchSession(sessionId, (s) => ({
    ...s,
    messages: s.messages.map((m) =>
      m.id === msgId ? { ...m, tools: [...(m.tools || []), event] } : m,
    ),
  }));
}

export function markMessageDone(sessionId: string, msgId: string) {
  touchSession(sessionId, (s) => ({
    ...s,
    messages: s.messages.map((m) =>
      m.id === msgId ? { ...m, streaming: false } : m,
    ),
  }));
}

export function addContextEntity(sessionId: string, entity: ContextEntity) {
  touchSession(sessionId, (s) => {
    // Dedup by entity.id — replace if exists to keep latest fields
    const existing = s.contextEntities.findIndex((e) => e.id === entity.id);
    let next: ContextEntity[];
    if (existing >= 0) {
      next = [...s.contextEntities];
      next[existing] = entity;
    } else {
      next = [entity, ...s.contextEntities].slice(0, 30);
    }
    return { ...s, contextEntities: next };
  });
}

export function removeContextEntity(sessionId: string, entityId: string) {
  touchSession(sessionId, (s) => ({
    ...s,
    contextEntities: s.contextEntities.filter((e) => e.id !== entityId),
  }));
}

export function clearContextEntities(sessionId: string) {
  touchSession(sessionId, (s) => ({ ...s, contextEntities: [] }));
}

export function autoTitleFromFirstMessage(sessionId: string) {
  const s = getSession(sessionId);
  if (!s || s.title !== "New Chat") return;
  const firstUser = s.messages.find((m) => m.role === "user");
  if (!firstUser) return;
  const title = firstUser.content.trim().slice(0, 40).replace(/\n+/g, " ");
  if (title) renameSession(sessionId, title);
}

// ═══════════════════════════════════════════
// React hook
// ═══════════════════════════════════════════

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

function getSnapshot(): StoreState {
  return state;
}

function getServerSnapshot(): StoreState {
  return { sessions: [], activeId: null };
}

export function useSessionStore() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const active = snapshot.activeId
    ? snapshot.sessions.find((s) => s.id === snapshot.activeId) ?? null
    : null;
  return {
    sessions: [...snapshot.sessions].sort((a, b) => b.updatedAt - a.updatedAt),
    activeId: snapshot.activeId,
    active,
    createSession,
    deleteSession,
    renameSession,
    setActiveId,
    addMessage,
    appendAssistantChunk,
    addToolEvent,
    markMessageDone,
    addContextEntity,
    removeContextEntity,
    clearContextEntities,
    autoTitleFromFirstMessage,
  };
}

// UI prefs (context panel collapsed state)
const UI_KEY = "bdgo.ui.contextCollapsed";

export function getContextCollapsed(): boolean {
  if (!isBrowser()) return false;
  return localStorage.getItem(UI_KEY) === "1";
}

export function setContextCollapsed(value: boolean) {
  if (!isBrowser()) return;
  if (value) localStorage.setItem(UI_KEY, "1");
  else localStorage.removeItem(UI_KEY);
}

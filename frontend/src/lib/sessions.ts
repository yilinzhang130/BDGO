"use client";

import { useSyncExternalStore } from "react";
import {
  fetchSessions,
  fetchSession,
  createSessionAPI,
  renameSessionAPI,
  deleteSessionAPI,
  postMessage,
  postEntity,
  deleteEntity,
} from "./api";
import { isBrowser, bg } from "./utils";
import { getToken } from "./auth";

// Types live in session-types.ts; re-exported here so all existing
// import { type X } from "@/lib/sessions" paths continue to work.
import type {
  Role,
  ToolEvent,
  ReportTask,
  PlanStep,
  PlanProposal,
  PlanStatus,
  ChatMessage,
  EntityType,
  ContextEntity,
  ChatSession,
  QuickSearchSource,
} from "./session-types";
export type {
  Role,
  ToolEvent,
  ReportTask,
  PlanStep,
  PlanProposal,
  PlanStatus,
  ChatMessage,
  EntityType,
  ContextEntity,
  ChatSession,
  QuickSearchSource,
} from "./session-types";

// Parse the tools_json column — it may hold either the legacy array of
// ToolEvent objects or an object with {plan, tools, ...} when the message
// is a plan proposal.
function parseStoredTools(raw: string | null | undefined): {
  tools?: any[];
  plan?: any;
  planStatus?: any;
  planSelectedIds?: string[];
  originalMessage?: string;
  quickSources?: QuickSearchSource[];
} {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return { tools: parsed };
    }
    if (parsed && typeof parsed === "object") {
      return {
        tools: parsed.tools,
        plan: parsed.plan,
        planStatus: parsed.planStatus || (parsed.plan ? "pending" : undefined),
        planSelectedIds: parsed.planSelectedIds,
        originalMessage: parsed.originalMessage || parsed.original_message,
        quickSources: parsed.kind === "quick_search" ? parsed.sources : undefined,
      };
    }
  } catch {}
  return {};
}

// Extract plain text from stored content (may be JSON content-blocks array)
function extractText(raw: string): string {
  if (!raw) return "";
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed
        .filter((b: any) => b.type === "text")
        .map((b: any) => b.text || "")
        .join("");
    }
  } catch {}
  return raw;
}

// ═══════════════════════════════════════════
// Store (module-level, server-backed with local cache)
// ═══════════════════════════════════════════

const ACTIVE_KEY = "bdgo.sessions.active";

interface StoreState {
  sessions: ChatSession[];
  activeId: string | null;
  _hydrated: boolean;
}

let state: StoreState = { sessions: [], activeId: null, _hydrated: false };
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function setLocalState(next: Partial<StoreState>) {
  state = { ...state, ...next };
  // Persist activeId locally (instant restore on reload)
  if (isBrowser()) {
    if (state.activeId) localStorage.setItem(ACTIVE_KEY, state.activeId);
    else localStorage.removeItem(ACTIVE_KEY);
  }
  emit();
}

function touchSession(id: string, mutator: (s: ChatSession) => ChatSession) {
  setLocalState({
    sessions: state.sessions.map((s) =>
      s.id === id ? { ...mutator(s), updatedAt: Date.now() } : s,
    ),
  });
}

// ═══════════════════════════════════════════
// Server hydration
// ═══════════════════════════════════════════

function mapServerSession(raw: any): ChatSession {
  return {
    id: raw.id,
    title: raw.title || "New Chat",
    createdAt: new Date(raw.created_at).getTime(),
    updatedAt: new Date(raw.updated_at).getTime(),
    messages: (raw.messages || []).map((m: any) => {
      const parsed = parseStoredTools(m.tools_json);
      return {
        id: m.id,
        role: m.role as Role,
        content: extractText(m.content || ""),
        tools: parsed.tools,
        plan: parsed.plan,
        planStatus: parsed.planStatus,
        planSelectedIds: parsed.planSelectedIds,
        originalMessage: parsed.originalMessage,
        quickSources: parsed.quickSources,
        attachments: m.attachments_json ? JSON.parse(m.attachments_json) : undefined,
        streaming: false,
        createdAt: new Date(m.created_at || raw.created_at).getTime(),
      };
    }),
    contextEntities: (raw.context_entities || []).map((e: any) => ({
      id: e.id,
      entityType: e.entity_type as EntityType,
      title: e.title,
      subtitle: e.subtitle || undefined,
      fields: e.fields_json ? JSON.parse(e.fields_json) : [],
      href: e.href || undefined,
      addedAt: new Date(e.created_at || raw.created_at).getTime(),
    })),
  };
}

function mapServerSessionSummary(raw: any): ChatSession {
  return {
    id: raw.id,
    title: raw.title || "New Chat",
    createdAt: new Date(raw.created_at).getTime(),
    updatedAt: new Date(raw.updated_at).getTime(),
    messages: [],
    contextEntities: [],
  };
}

let hydratePromise: Promise<void> | null = null;

function hydrateFromServer() {
  if (hydratePromise) return hydratePromise;
  hydratePromise = (async () => {
    try {
      const list = await fetchSessions();
      const sessions = list.map(mapServerSessionSummary);
      // Restore activeId from localStorage
      const savedActive = isBrowser() ? localStorage.getItem(ACTIVE_KEY) : null;
      const activeId =
        savedActive && sessions.some((s) => s.id === savedActive)
          ? savedActive
          : sessions.length > 0
            ? sessions[0].id
            : null;
      setLocalState({ sessions, activeId, _hydrated: true });

      // Eagerly load the active session's full data
      if (activeId) {
        loadSessionDetail(activeId);
      }
    } catch (err) {
      console.error("[sessions] hydrate failed:", err);
      setLocalState({ _hydrated: true });
    }
  })();
  return hydratePromise;
}

const loadedSessionIds = new Set<string>();

async function loadSessionDetail(id: string) {
  if (loadedSessionIds.has(id)) return;
  loadedSessionIds.add(id);
  try {
    const raw = await fetchSession(id);
    const full = mapServerSession(raw);
    setLocalState({
      sessions: state.sessions.map((s) => (s.id === id ? full : s)),
    });
  } catch (err) {
    console.error(`[sessions] load detail ${id}:`, err);
    loadedSessionIds.delete(id);
  }
}

// Initial hydration (skip API call if not logged in to avoid guaranteed 401)
if (isBrowser()) {
  state.activeId = localStorage.getItem(ACTIVE_KEY);
  if (getToken()) hydrateFromServer();
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
  setLocalState({ activeId: id });
  // Load full session data if we haven't yet
  if (id) loadSessionDetail(id);
}

export function createSession(title = "New Chat"): ChatSession {
  const now = Date.now();
  const tempId = genId();
  const session: ChatSession = {
    id: tempId,
    title,
    createdAt: now,
    updatedAt: now,
    messages: [],
    contextEntities: [],
  };
  // Optimistic: add locally immediately
  setLocalState({
    sessions: [session, ...state.sessions],
    activeId: session.id,
  });
  loadedSessionIds.add(tempId);

  // Server: create and update the ID if server assigns a different one
  bg(
    createSessionAPI(title).then((res) => {
      if (res.id && res.id !== tempId) {
        const serverId = res.id;
        loadedSessionIds.delete(tempId);
        loadedSessionIds.add(serverId);
        setLocalState({
          sessions: state.sessions.map((s) =>
            s.id === tempId ? { ...s, id: serverId } : s,
          ),
          activeId: state.activeId === tempId ? serverId : state.activeId,
        });
        session.id = serverId;
      }
    }),
    "createSession",
  );
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
  setLocalState({ sessions: remaining, activeId: nextActive });
  loadedSessionIds.delete(id);
  bg(deleteSessionAPI(id), "deleteSession");
}

export function renameSession(id: string, title: string) {
  const cleaned = title.trim() || "New Chat";
  setLocalState({
    sessions: state.sessions.map((s) =>
      s.id === id ? { ...s, title: cleaned, updatedAt: Date.now() } : s,
    ),
  });
  bg(renameSessionAPI(id, cleaned), "renameSession");
}

export function addMessage(sessionId: string, msg: ChatMessage) {
  touchSession(sessionId, (s) => ({
    ...s,
    messages: [...s.messages, msg],
  }));

  // Only persist non-streaming user messages immediately
  if (msg.role === "user") {
    bg(
      postMessage(sessionId, {
        id: msg.id,
        role: msg.role,
        content: msg.content,
        attachments_json: msg.attachments ? JSON.stringify(msg.attachments) : undefined,
      }),
      "addMessage",
    );
  }
}

export function appendAssistantChunk(
  sessionId: string,
  msgId: string,
  chunk: string,
) {
  // Local-only during streaming — saved on markMessageDone
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

export function addReportTask(
  sessionId: string,
  msgId: string,
  task: ReportTask,
) {
  touchSession(sessionId, (s) => ({
    ...s,
    messages: s.messages.map((m) =>
      m.id === msgId
        ? { ...m, reportTasks: [...(m.reportTasks || []), task] }
        : m,
    ),
  }));
}

export function setMessageQuickSources(
  sessionId: string,
  msgId: string,
  sources: QuickSearchSource[],
) {
  touchSession(sessionId, (s) => ({
    ...s,
    messages: s.messages.map((m) =>
      m.id === msgId ? { ...m, quickSources: sources } : m,
    ),
  }));
}

export function setMessageError(
  sessionId: string,
  msgId: string,
  error: string,
) {
  touchSession(sessionId, (s) => ({
    ...s,
    messages: s.messages.map((m) =>
      m.id === msgId ? { ...m, error, streaming: false } : m,
    ),
  }));
}

export function removeMessage(sessionId: string, msgId: string) {
  touchSession(sessionId, (s) => ({
    ...s,
    messages: s.messages.filter((m) => m.id !== msgId),
  }));
}

export function markMessageDone(sessionId: string, msgId: string) {
  touchSession(sessionId, (s) => ({
    ...s,
    messages: s.messages.map((m) =>
      m.id === msgId ? { ...m, streaming: false } : m,
    ),
  }));

  // Persist the completed assistant message to server.
  // Errored messages stay client-side only so a retry doesn't leave
  // the failed turn in the DB.
  const session = getSession(sessionId);
  const msg = session?.messages.find((m) => m.id === msgId);
  if (msg && msg.role === "assistant" && !msg.error) {
    const toolsJson = msg.plan
      ? JSON.stringify({
          plan: msg.plan,
          planStatus: msg.planStatus,
          planSelectedIds: msg.planSelectedIds,
          originalMessage: msg.originalMessage,
          tools: msg.tools,
        })
      : msg.quickSources
      ? JSON.stringify({ kind: "quick_search", sources: msg.quickSources })
      : msg.tools
      ? JSON.stringify(msg.tools)
      : undefined;
    bg(
      postMessage(sessionId, {
        id: msg.id,
        role: msg.role,
        content: msg.content,
        tools_json: toolsJson,
        attachments_json: msg.attachments ? JSON.stringify(msg.attachments) : undefined,
      }),
      "markMessageDone",
    );
  }
}

export function setMessagePlan(
  sessionId: string,
  msgId: string,
  plan: PlanProposal,
  originalMessage: string,
) {
  touchSession(sessionId, (s) => ({
    ...s,
    messages: s.messages.map((m) =>
      m.id === msgId
        ? {
            ...m,
            plan,
            planStatus: "pending" as PlanStatus,
            originalMessage,
            streaming: false,
          }
        : m,
    ),
  }));
}

export function updatePlanStatus(
  sessionId: string,
  msgId: string,
  status: PlanStatus,
  selectedIds?: string[],
) {
  touchSession(sessionId, (s) => ({
    ...s,
    messages: s.messages.map((m) =>
      m.id === msgId
        ? { ...m, planStatus: status, planSelectedIds: selectedIds ?? m.planSelectedIds }
        : m,
    ),
  }));
}

export function addContextEntity(sessionId: string, entity: ContextEntity) {
  touchSession(sessionId, (s) => {
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
  bg(
    postEntity(sessionId, {
      id: entity.id,
      entity_type: entity.entityType,
      title: entity.title,
      subtitle: entity.subtitle,
      fields_json: JSON.stringify(entity.fields),
      href: entity.href,
    }),
    "addContextEntity",
  );
}

export function removeContextEntity(sessionId: string, entityId: string) {
  touchSession(sessionId, (s) => ({
    ...s,
    contextEntities: s.contextEntities.filter((e) => e.id !== entityId),
  }));
  bg(deleteEntity(sessionId, entityId), "removeContextEntity");
}

export function clearContextEntities(sessionId: string) {
  const session = getSession(sessionId);
  const entityIds = session?.contextEntities.map((e) => e.id) || [];
  touchSession(sessionId, (s) => ({ ...s, contextEntities: [] }));
  // Delete each entity on server
  for (const eid of entityIds) {
    bg(deleteEntity(sessionId, eid), "clearContextEntities");
  }
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

const _serverSnapshot: StoreState = { sessions: [], activeId: null, _hydrated: false };
function getServerSnapshot(): StoreState {
  return _serverSnapshot;
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
    addReportTask,
    markMessageDone,
    setMessagePlan,
    setMessageQuickSources,
    setMessageError,
    removeMessage,
    updatePlanStatus,
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

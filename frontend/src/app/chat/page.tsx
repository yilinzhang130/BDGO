"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import {
  uploadBP,
  fetchReportServices,
  parseReportArgs,
  generateReport,
  type PlanMode,
  type SearchMode,
} from "@/lib/api";
import {
  useSessionStore,
  getContextCollapsed,
  setContextCollapsed as persistCollapsed,
} from "@/lib/sessions";
import { ChatMessage } from "@/components/ui/ChatMessage";
import { ContextPanel } from "@/components/ui/ContextPanel";
import { Sidebar } from "@/components/ui/Sidebar";
import { ModelPicker } from "@/components/ui/ModelPicker";
import { ReportGenerateDialog, type ReportService } from "@/components/ui/ReportGenerateDialog";
import {
  SLASH_COMMANDS,
  type SlashCommand,
} from "@/components/ui/SlashCommandPopup";
import { autoTitleFromFirstMessage } from "@/lib/sessions";
import { useChatStream } from "@/hooks/useChatStream";
import { ChatHeaderControls } from "@/components/chat/ChatHeaderControls";
import { ChatInputBar } from "@/components/chat/ChatInputBar";

const SUGGESTIONS = [
  "AbbVie\u6709\u51E0\u4E2A Phase 3 \u7684\u8D44\u4EA7\uFF1F",
  "\u5E2E\u6211\u5206\u6790\u4E00\u4E0B Biogen \u7684\u7BA1\u7EBF",
  "\u8FD1\u671F\u6700\u5927\u7684 BD \u4EA4\u6613\u662F\u54EA\u4E2A\uFF1F",
  "\u6309\u9636\u6BB5\u7EDF\u8BA1\u8D44\u4EA7\u6570\u91CF",
];

export default function ChatPage() {
  const {
    active,
    activeId,
    createSession,
    addMessage,
    markMessageDone,
    removeMessage,
    updatePlanStatus,
    addReportTask,
    removeContextEntity,
    clearContextEntities,
    renameSession,
  } = useSessionStore();

  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [contextCollapsed, setCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [logoReady, setLogoReady] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [editingTitle, setEditingTitle] = useState(false);
  const [planMode, setPlanMode] = useState<PlanMode>("auto");
  const [searchMode, setSearchMode] = useState<SearchMode>("agent");

  const [reportServices, setReportServices] = useState<ReportService[]>([]);
  const [slashActiveIndex, setSlashActiveIndex] = useState(0);
  const [selectedServiceForDialog, setSelectedServiceForDialog] = useState<ReportService | null>(null);
  const [slashPrefillParams, setSlashPrefillParams] = useState<Record<string, unknown>>({});
  const [slashParsing, setSlashParsing] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);

  const { streamInto, isStreaming } = useChatStream();

  // Hydrate client-only state
  useEffect(() => {
    setHydrated(true);
    setCollapsed(getContextCollapsed());
    try {
      const stored = localStorage.getItem("bdgo.planMode");
      if (stored === "auto" || stored === "on" || stored === "off") setPlanMode(stored);
      const storedSearch = localStorage.getItem("bdgo.searchMode");
      if (storedSearch === "agent" || storedSearch === "quick") setSearchMode(storedSearch);
    } catch {}
    if (!activeId) createSession();
    const probe = new Image();
    probe.onload = () => { if (probe.naturalWidth > 0) setLogoReady(true); };
    probe.src = "/logo.png";
    fetchReportServices()
      .then((data) => {
        const d = data as { services?: ReportService[] };
        setReportServices(d?.services || []);
      })
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Merge static alias list with fetched service metadata to get display names.
  const slashCommandsAll = useMemo<SlashCommand[]>(() => {
    return SLASH_COMMANDS.map((base) => {
      const svc = reportServices.find((s) => s.slug === base.slug);
      return {
        alias: base.alias,
        slug: base.slug,
        displayName: svc?.display_name || base.slug,
        description: svc?.description || "",
        estimatedSeconds: svc?.estimated_seconds,
      };
    });
  }, [reportServices]);

  const cyclePlanMode = () => {
    const next: PlanMode = planMode === "auto" ? "on" : planMode === "on" ? "off" : "auto";
    setPlanMode(next);
    try { localStorage.setItem("bdgo.planMode", next); } catch {}
  };

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [active?.messages]);

  const handleFileUpload = async (file: File) => {
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!["pdf", "pptx", "ppt", "docx", "doc"].includes(ext || "")) {
      alert("Unsupported file type. Please upload PDF, PPTX, or DOCX.");
      return;
    }
    setUploading(true);
    try {
      const res = await uploadBP(file);
      setAttachments((prev) => [...prev, res.filename]);
    } catch (e: unknown) {
      alert(`Upload failed: ${(e as Error).message}`);
    } finally {
      setUploading(false);
    }
  };

  const removeAttachment = (filename: string) => {
    setAttachments((prev) => prev.filter((f) => f !== filename));
  };

  const handleToggleCollapse = () => {
    const next = !contextCollapsed;
    setCollapsed(next);
    persistCollapsed(next);
  };

  const handleSend = useCallback(
    async (text?: string) => {
      const msg = (text || input).trim();
      if (!msg || isStreaming || !activeId) return;

      const targetSessionId = activeId;
      const currentFiles = [...attachments];

      setInput("");
      setAttachments([]);

      const userMsgId = crypto.randomUUID().slice(0, 12);
      const assistantMsgId = crypto.randomUUID().slice(0, 12);

      addMessage(targetSessionId, {
        id: userMsgId,
        role: "user",
        content: msg,
        attachments: currentFiles.length > 0 ? currentFiles : undefined,
        createdAt: Date.now(),
      });
      addMessage(targetSessionId, {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        tools: [],
        streaming: true,
        createdAt: Date.now(),
      });

      await streamInto({
        targetSessionId,
        assistantMsgId,
        message: msg,
        files: currentFiles,
        planModeOverride: planMode,
        searchModeOverride: searchMode,
      });
    },
    [input, isStreaming, activeId, attachments, addMessage, streamInto, planMode, searchMode],
  );

  // Retry an errored assistant reply: delete the errored message and
  // re-send the user turn immediately before it. Preserves attachments.
  const handleRetry = useCallback(
    async (erroredMsgId: string) => {
      if (!activeId || isStreaming) return;
      const session = active;
      if (!session) return;
      const idx = session.messages.findIndex((m) => m.id === erroredMsgId);
      if (idx <= 0) return;
      let userIdx = idx - 1;
      while (userIdx >= 0 && session.messages[userIdx].role !== "user") userIdx--;
      if (userIdx < 0) return;
      const userMsg = session.messages[userIdx];

      removeMessage(activeId, erroredMsgId);
      const assistantMsgId = crypto.randomUUID().slice(0, 12);
      addMessage(activeId, {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        tools: [],
        streaming: true,
        createdAt: Date.now(),
      });

      await streamInto({
        targetSessionId: activeId,
        assistantMsgId,
        message: userMsg.content,
        files: userMsg.attachments || [],
        planModeOverride: planMode,
        searchModeOverride: searchMode,
      });
    },
    [activeId, active, isStreaming, addMessage, removeMessage, streamInto, planMode, searchMode],
  );

  const handlePlanConfirm = useCallback(
    async (planMsgId: string, selectedStepIds: string[]) => {
      const currentSession = activeId;
      if (!currentSession) return;
      const session = active;
      const planMsg = session?.messages.find((m) => m.id === planMsgId);
      if (!planMsg || !planMsg.plan || !planMsg.originalMessage) return;

      const selectedSteps = planMsg.plan.steps
        .filter((s) => selectedStepIds.includes(s.id) || s.required)
        .map((s) => ({
          id: s.id,
          title: s.title,
          description: s.description,
          tools_expected: s.tools_expected,
        }));

      updatePlanStatus(currentSession, planMsgId, "confirmed", selectedSteps.map((s) => s.id));

      const executionMsgId = crypto.randomUUID().slice(0, 12);
      addMessage(currentSession, {
        id: executionMsgId,
        role: "assistant",
        content: "",
        tools: [],
        streaming: true,
        createdAt: Date.now(),
      });

      await streamInto({
        targetSessionId: currentSession,
        assistantMsgId: executionMsgId,
        message: planMsg.originalMessage,
        files: [],
        planModeOverride: "off",
        planConfirm: {
          plan_id: planMsg.plan.plan_id,
          plan_title: planMsg.plan.title,
          selected_steps: selectedSteps,
          original_message: planMsg.originalMessage,
        },
      });
    },
    [activeId, active, updatePlanStatus, addMessage, streamInto],
  );

  const handlePlanSkip = useCallback(
    async (planMsgId: string) => {
      const currentSession = activeId;
      if (!currentSession) return;
      const session = active;
      const planMsg = session?.messages.find((m) => m.id === planMsgId);
      if (!planMsg || !planMsg.originalMessage) return;

      updatePlanStatus(currentSession, planMsgId, "cancelled");

      const executionMsgId = crypto.randomUUID().slice(0, 12);
      addMessage(currentSession, {
        id: executionMsgId,
        role: "assistant",
        content: "",
        tools: [],
        streaming: true,
        createdAt: Date.now(),
      });

      await streamInto({
        targetSessionId: currentSession,
        assistantMsgId: executionMsgId,
        message: planMsg.originalMessage,
        files: [],
        planModeOverride: "off",
      });
    },
    [activeId, active, updatePlanStatus, addMessage, streamInto],
  );

  const handleReportStarted = useCallback(
    (info: { task_id: string; slug: string; estimated_seconds: number; params: Record<string, unknown> }) => {
      const currentSession = activeId;
      if (!currentSession) return;
      const svc = reportServices.find((s) => s.slug === info.slug);
      const displayName = svc?.display_name || info.slug;

      const paramSummary = Object.entries(info.params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "" && v !== false)
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");

      const userMsgId = crypto.randomUUID().slice(0, 12);
      const assistantMsgId = crypto.randomUUID().slice(0, 12);

      addMessage(currentSession, {
        id: userMsgId,
        role: "user",
        content: `生成 ${displayName}${paramSummary ? `（${paramSummary}）` : ""}`,
        createdAt: Date.now(),
      });
      addMessage(currentSession, {
        id: assistantMsgId,
        role: "assistant",
        content: `正在生成 **${displayName}**，完成后会附下载链接。`,
        tools: [],
        streaming: false,
        createdAt: Date.now(),
      });
      addReportTask(currentSession, assistantMsgId, {
        task_id: info.task_id,
        slug: info.slug,
        estimated_seconds: info.estimated_seconds,
      });
      markMessageDone(currentSession, assistantMsgId);
      autoTitleFromFirstMessage(currentSession);
      setSelectedServiceForDialog(null);
    },
    [activeId, reportServices, addMessage, addReportTask, markMessageDone],
  );

  // "/mnc" opens the dialog blank; "/mnc 辉瑞 ..." runs an LLM parse first
  // and skips the dialog when every required field can be extracted.
  const handleSlashSelect = useCallback(
    async (cmd: SlashCommand) => {
      const svc = reportServices.find((s) => s.slug === cmd.slug);
      if (!svc) {
        setInput(`/${cmd.alias} `);
        return;
      }

      const rest = input.startsWith("/")
        ? input.slice(1).replace(/^\S+\s*/, "").trim()
        : "";

      if (!rest) {
        setInput("");
        setSlashPrefillParams({});
        setSelectedServiceForDialog(svc);
        return;
      }

      setSlashParsing(true);
      setInput("");
      try {
        const parsed = await parseReportArgs(cmd.slug, rest);
        if (parsed.complete) {
          const resp = (await generateReport(cmd.slug, parsed.params)) as { task_id: string };
          handleReportStarted({
            task_id: resp.task_id,
            slug: cmd.slug,
            estimated_seconds: svc.estimated_seconds ?? 60,
            params: parsed.params,
          });
          return;
        }
        setSlashPrefillParams(parsed.params || {});
        setSelectedServiceForDialog(svc);
      } catch {
        setSlashPrefillParams({});
        setSelectedServiceForDialog(svc);
      } finally {
        setSlashParsing(false);
      }
    },
    [reportServices, input, handleReportStarted],
  );

  const handlePlanCancel = useCallback(
    (planMsgId: string) => {
      const currentSession = activeId;
      if (!currentSession) return;
      updatePlanStatus(currentSession, planMsgId, "cancelled");
    },
    [activeId, updatePlanStatus],
  );

  const startTitleEdit = () => {
    if (!active) return;
    setTitleDraft(active.title);
    setEditingTitle(true);
  };

  const saveTitleEdit = () => {
    if (activeId && titleDraft.trim()) {
      renameSession(activeId, titleDraft.trim());
    }
    setEditingTitle(false);
  };

  if (!hydrated) {
    return (
      <div className="chat-shell">
        <Sidebar />
        <div className="chat-center">
          <div className="loading">Loading...</div>
        </div>
      </div>
    );
  }

  const messages = active?.messages ?? [];
  const entities = active?.contextEntities ?? [];
  const isEmpty = messages.length === 0;

  return (
    <div className={`chat-shell ${contextCollapsed ? "context-collapsed" : ""}`}>
      <Sidebar />

      <section className="chat-center">
        <header className="chat-header">
          {editingTitle ? (
            <input
              autoFocus
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={saveTitleEdit}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveTitleEdit();
                if (e.key === "Escape") setEditingTitle(false);
              }}
              className="chat-header-title"
              style={{ borderBottom: "1px solid var(--accent)" }}
            />
          ) : (
            <div
              className="chat-header-title"
              onClick={startTitleEdit}
              title="Click to rename"
              style={{ cursor: "pointer" }}
            >
              {active?.title || "New Chat"}
            </div>
          )}
          <div className="chat-header-actions">
            <ModelPicker compact />
            <ChatHeaderControls
              searchMode={searchMode}
              onSearchModeChange={(m) => {
                setSearchMode(m);
                try { localStorage.setItem("bdgo.searchMode", m); } catch {}
              }}
              planMode={planMode}
              onCyclePlanMode={cyclePlanMode}
            />
            {contextCollapsed && (
              <button
                className="icon-btn"
                onClick={handleToggleCollapse}
                title="Show context panel"
              >
                {"\u2039"}
              </button>
            )}
          </div>
        </header>

        <div className="chat-history" ref={scrollRef}>
          {isEmpty ? (
            <div className="chat-empty">
              {logoReady && (
                <img
                  src="/logo.png"
                  alt="BD Go"
                  className="chat-empty-logo"
                />
              )}
              <h1 className="chat-title">
                <span className="brand-bd">BD</span>
                <span className="brand-go"> Go</span>
              </h1>
              <p className="chat-subtitle">Biotech BD Intelligence Assistant</p>
              <div className="chat-suggestions">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    className="chat-suggestion"
                    onClick={() => handleSend(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="chat-messages">
              {messages.map((m) => (
                <ChatMessage
                  key={m.id}
                  role={m.role}
                  content={m.content}
                  streaming={m.streaming}
                  tools={m.tools}
                  attachments={m.attachments}
                  reportTasks={m.reportTasks}
                  plan={m.plan}
                  planStatus={m.planStatus}
                  planSelectedIds={m.planSelectedIds}
                  quickSources={m.quickSources}
                  error={m.error}
                  onRetry={() => handleRetry(m.id)}
                  onPlanConfirm={(ids) => handlePlanConfirm(m.id, ids)}
                  onPlanSkip={() => handlePlanSkip(m.id)}
                  onPlanCancel={() => handlePlanCancel(m.id)}
                />
              ))}
            </div>
          )}
        </div>

        <ChatInputBar
          input={input}
          onInputChange={setInput}
          attachments={attachments}
          onRemoveAttachment={removeAttachment}
          onPickFile={handleFileUpload}
          uploading={uploading}
          isStreaming={isStreaming}
          slashParsing={slashParsing}
          onSend={() => handleSend()}
          slashCommands={slashCommandsAll}
          slashActiveIndex={slashActiveIndex}
          onSlashActiveIndexChange={setSlashActiveIndex}
          onSlashSelect={handleSlashSelect}
        />
      </section>

      {selectedServiceForDialog && (
        <ReportGenerateDialog
          service={selectedServiceForDialog}
          onClose={() => setSelectedServiceForDialog(null)}
          onStarted={handleReportStarted}
          initialParams={slashPrefillParams}
        />
      )}

      {!contextCollapsed && activeId && (
        <ContextPanel
          entities={entities}
          onRemove={(id) => removeContextEntity(activeId, id)}
          onClear={() => clearContextEntities(activeId)}
          onCollapse={handleToggleCollapse}
        />
      )}
    </div>
  );
}

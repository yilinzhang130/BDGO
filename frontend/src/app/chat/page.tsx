"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { chatStream, uploadBP, fetchReportServices, parseReportArgs, generateReport, type PlanMode, type PlanConfirmPayload, type SearchMode } from "@/lib/api";
import {
  useSessionStore,
  getContextCollapsed,
  setContextCollapsed as persistCollapsed,
  autoTitleFromFirstMessage,
  type ContextEntity,
} from "@/lib/sessions";
import { ChatMessage } from "@/components/ui/ChatMessage";
import { ContextPanel } from "@/components/ui/ContextPanel";
import { Sidebar } from "@/components/ui/Sidebar";
import { ModelPicker } from "@/components/ui/ModelPicker";
import { ReportGenerateDialog } from "@/components/ui/ReportGenerateDialog";
import {
  SlashCommandPopup,
  SLASH_COMMANDS,
  filterCommands,
  type SlashCommand,
} from "@/components/ui/SlashCommandPopup";
import { getSelectedModel, applyCreditsUsage, refreshCredits } from "@/lib/credits";

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
    appendAssistantChunk,
    addToolEvent,
    addReportTask,
    markMessageDone,
    setMessagePlan,
    setMessageQuickSources,
    updatePlanStatus,
    addContextEntity,
    removeContextEntity,
    clearContextEntities,
    renameSession,
  } = useSessionStore();

  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [attachments, setAttachments] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [contextCollapsed, setCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [logoReady, setLogoReady] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [editingTitle, setEditingTitle] = useState(false);
  const [planMode, setPlanMode] = useState<PlanMode>("auto");
  const [searchMode, setSearchMode] = useState<SearchMode>("agent");

  // Slash command state
  const [reportServices, setReportServices] = useState<any[]>([]);
  const [slashActiveIndex, setSlashActiveIndex] = useState(0);
  const [selectedServiceForDialog, setSelectedServiceForDialog] = useState<any | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Hydrate client-only state
  useEffect(() => {
    setHydrated(true);
    setCollapsed(getContextCollapsed());
    // Restore plan mode preference from localStorage
    try {
      const stored = localStorage.getItem("bdgo.planMode");
      if (stored === "auto" || stored === "on" || stored === "off") {
        setPlanMode(stored);
      }
      const storedSearch = localStorage.getItem("bdgo.searchMode");
      if (storedSearch === "agent" || storedSearch === "quick") {
        setSearchMode(storedSearch);
      }
    } catch {}
    // Ensure at least one session exists
    if (!activeId) {
      createSession();
    }
    // Probe for logo.png
    const probe = new Image();
    probe.onload = () => { if (probe.naturalWidth > 0) setLogoReady(true); };
    probe.src = "/logo.png";
    // Load report service catalog once — powers the slash command popup
    fetchReportServices()
      .then((data: any) => setReportServices(data?.services || []))
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

  // Derive popup state from the current input text.
  const slashQuery = input.startsWith("/") ? input.slice(1).split(/\s/)[0] : null;
  const slashOpen = slashQuery !== null && !isStreaming;
  const filteredSlashCommands = useMemo(
    () => (slashQuery === null ? [] : filterCommands(slashCommandsAll, slashQuery)),
    [slashCommandsAll, slashQuery],
  );

  // Clamp active index whenever the filtered list shrinks.
  useEffect(() => {
    if (slashActiveIndex >= filteredSlashCommands.length && filteredSlashCommands.length > 0) {
      setSlashActiveIndex(0);
    }
  }, [filteredSlashCommands.length, slashActiveIndex]);

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

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 140) + "px";
    }
  }, [input]);

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
    } catch (e: any) {
      alert(`Upload failed: ${e.message}`);
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

  // Low-level streamer — shared by new sends and plan confirmation/skip.
  // Caller provides the targetSessionId, assistantMsgId (pre-created), and options.
  const streamInto = useCallback(
    async (opts: {
      targetSessionId: string;
      assistantMsgId: string;
      message: string;
      files: string[];
      planModeOverride: PlanMode;
      planConfirm?: PlanConfirmPayload;
      searchModeOverride?: SearchMode;
    }) => {
      const { targetSessionId, assistantMsgId, message, files, planModeOverride, planConfirm, searchModeOverride } = opts;
      setIsStreaming(true);
      try {
        const res = await chatStream(
          message,
          targetSessionId,
          files,
          getSelectedModel() || undefined,
          planModeOverride,
          planConfirm,
          searchModeOverride ?? "agent",
        );
        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response stream");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          while (buffer.includes("\n\n")) {
            const eventEnd = buffer.indexOf("\n\n");
            const eventText = buffer.slice(0, eventEnd);
            buffer = buffer.slice(eventEnd + 2);

            for (const line of eventText.split("\n")) {
              if (!line.startsWith("data: ")) continue;
              try {
                const data = JSON.parse(line.slice(6));

                if (data.type === "chunk") {
                  appendAssistantChunk(targetSessionId, assistantMsgId, data.content);
                } else if (data.type === "tool_call") {
                  addToolEvent(targetSessionId, assistantMsgId, { type: "tool_call", name: data.name });
                } else if (data.type === "tool_result") {
                  addToolEvent(targetSessionId, assistantMsgId, { type: "tool_result", name: data.name });
                } else if (data.type === "report_task") {
                  addReportTask(targetSessionId, assistantMsgId, {
                    task_id: data.task_id,
                    slug: data.slug,
                    estimated_seconds: data.estimated_seconds,
                  });
                } else if (data.type === "plan_proposal") {
                  setMessagePlan(
                    targetSessionId,
                    assistantMsgId,
                    data.plan,
                    data.original_message || message,
                  );
                } else if (data.type === "quick_sources") {
                  setMessageQuickSources(
                    targetSessionId,
                    assistantMsgId,
                    data.sources || [],
                  );
                } else if (data.type === "context_entity") {
                  const entity: ContextEntity = {
                    id: data.id,
                    entityType: data.entity_type,
                    title: data.title,
                    subtitle: data.subtitle,
                    fields: data.fields || [],
                    href: data.href,
                    addedAt: Date.now(),
                  };
                  addContextEntity(targetSessionId, entity);
                } else if (data.type === "error") {
                  appendAssistantChunk(targetSessionId, assistantMsgId, `\n\n**Error:** ${data.message}`);
                  markMessageDone(targetSessionId, assistantMsgId);
                } else if (data.type === "usage") {
                  applyCreditsUsage(data.credits_charged ?? 0, data.balance ?? null);
                } else if (data.type === "done") {
                  markMessageDone(targetSessionId, assistantMsgId);
                  void refreshCredits();
                }
              } catch {
                /* ignore parse errors */
              }
            }
          }
        }
      } catch (e: any) {
        appendAssistantChunk(targetSessionId, assistantMsgId, `\n\nConnection error: ${e.message}`);
        markMessageDone(targetSessionId, assistantMsgId);
      } finally {
        setIsStreaming(false);
        markMessageDone(targetSessionId, assistantMsgId);
        autoTitleFromFirstMessage(targetSessionId);
      }
    },
    [
      appendAssistantChunk,
      addToolEvent,
      addReportTask,
      setMessagePlan,
      setMessageQuickSources,
      addContextEntity,
      markMessageDone,
    ],
  );

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

  // User confirmed / skipped / cancelled a plan card.
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

      // Mark the plan card as confirmed (freezes its UI)
      updatePlanStatus(currentSession, planMsgId, "confirmed", selectedSteps.map((s) => s.id));

      // Create a new assistant message for the actual execution stream
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

  const [slashPrefillParams, setSlashPrefillParams] = useState<Record<string, any>>({});
  const [slashParsing, setSlashParsing] = useState(false);

  const handleReportStarted = useCallback(
    (info: { task_id: string; slug: string; estimated_seconds: number; params: Record<string, any> }) => {
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
        inputRef.current?.focus();
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
          const resp: any = await generateReport(cmd.slug, parsed.params);
          handleReportStarted({
            task_id: resp.task_id,
            slug: cmd.slug,
            estimated_seconds: svc.estimated_seconds,
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
            <div
              role="group"
              aria-label="搜索模式"
              style={{
                display: "inline-flex", borderRadius: 8,
                border: "1px solid #E2E8F0", overflow: "hidden",
              }}
            >
              {(["agent", "quick"] as const).map((m) => {
                const on = searchMode === m;
                return (
                  <button
                    key={m}
                    onClick={() => {
                      setSearchMode(m);
                      try { localStorage.setItem("bdgo.searchMode", m); } catch {}
                    }}
                    title={
                      m === "agent"
                        ? "Agent · 调用工具、CRM、报告生成（复杂任务）"
                        : "Quick · Tavily搜索+总结，低延迟（查事实/新闻）"
                    }
                    style={{
                      padding: "4px 10px", fontSize: 12, fontWeight: 500,
                      background: on ? (m === "quick" ? "#ECFDF5" : "#F8FAFF") : "#fff",
                      color: on ? (m === "quick" ? "#059669" : "#1E3A8A") : "#64748B",
                      border: "none",
                      borderRight: m === "agent" ? "1px solid #E2E8F0" : "none",
                      cursor: "pointer",
                    }}
                  >
                    {m === "agent" ? "🤖 Agent" : "⚡ Quick"}
                  </button>
                );
              })}
            </div>
            <button
              onClick={cyclePlanMode}
              title={
                planMode === "auto"
                  ? "规划模式：智能判断（长任务自动先规划）"
                  : planMode === "on"
                  ? "规划模式：始终先出方案"
                  : "规划模式：关闭（直接执行）"
              }
              style={{
                display: "inline-flex", alignItems: "center", gap: 4,
                padding: "4px 10px", fontSize: 12, fontWeight: 500,
                background: planMode === "on" ? "#DBEAFE" : planMode === "off" ? "#F1F5F9" : "#F8FAFF",
                border: `1px solid ${planMode === "on" ? "#1E3A8A" : "#E2E8F0"}`,
                color: planMode === "on" ? "#1E3A8A" : planMode === "off" ? "#64748B" : "#475569",
                borderRadius: 8, cursor: "pointer",
              }}
            >
              📋
              <span>
                {planMode === "auto" ? "规划 · 自动" : planMode === "on" ? "规划 · 开" : "规划 · 关"}
              </span>
            </button>
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
                  onPlanConfirm={(ids) => handlePlanConfirm(m.id, ids)}
                  onPlanSkip={() => handlePlanSkip(m.id)}
                  onPlanCancel={() => handlePlanCancel(m.id)}
                />
              ))}
            </div>
          )}
        </div>

        <div className="chat-input-wrapper">
          <div className="chat-input-container">
            {attachments.length > 0 && (
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "0.4rem",
                  padding: "0.3rem 0.35rem 0.5rem",
                }}
              >
                {attachments.map((f) => (
                  <div key={f} className="attachment-chip">
                    <span>{"\uD83D\uDCCE"} {f}</span>
                    <button
                      onClick={() => removeAttachment(f)}
                      className="attachment-chip-remove"
                    >
                      {"\u00D7"}
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="chat-input-bar">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.pptx,.ppt,.docx,.doc"
                style={{ display: "none" }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFileUpload(f);
                  e.target.value = "";
                }}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading || isStreaming}
                title="Attach file"
                className="chat-attach-btn"
              >
                {uploading ? "\u2026" : "\uD83D\uDCCE"}
              </button>
              <div style={{ flex: 1, position: "relative" }}>
                {slashOpen && (
                  <SlashCommandPopup
                    commands={filteredSlashCommands}
                    activeIndex={slashActiveIndex}
                    onSelect={handleSlashSelect}
                    onHover={setSlashActiveIndex}
                  />
                )}
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (slashOpen && filteredSlashCommands.length > 0) {
                      if (e.key === "ArrowDown") {
                        e.preventDefault();
                        setSlashActiveIndex((i) => (i + 1) % filteredSlashCommands.length);
                        return;
                      }
                      if (e.key === "ArrowUp") {
                        e.preventDefault();
                        setSlashActiveIndex((i) =>
                          (i - 1 + filteredSlashCommands.length) % filteredSlashCommands.length,
                        );
                        return;
                      }
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSlashSelect(filteredSlashCommands[slashActiveIndex]);
                        return;
                      }
                      if (e.key === "Tab") {
                        e.preventDefault();
                        handleSlashSelect(filteredSlashCommands[slashActiveIndex]);
                        return;
                      }
                      if (e.key === "Escape") {
                        e.preventDefault();
                        setInput("");
                        return;
                      }
                    }
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      if (input.startsWith("/")) return;
                      if (input.trim() && !isStreaming) handleSend();
                    }
                  }}
                  placeholder={
                    slashParsing
                      ? "解析参数中…"
                      : attachments.length > 0
                      ? "Ask about the attached files..."
                      : "Ask anything, or type / for report commands..."
                  }
                  disabled={isStreaming || slashParsing}
                  rows={1}
                  style={{ width: "100%" }}
                />
              </div>
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || isStreaming || input.startsWith("/")}
                className="chat-send-btn"
              >
                {isStreaming ? "\u2026" : "\u2191"}
              </button>
            </div>
          </div>
        </div>
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

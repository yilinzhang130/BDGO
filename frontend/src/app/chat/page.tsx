"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { uploadBP, type PlanMode, type SearchMode } from "@/lib/api";
import {
  useSessionStore,
  getContextCollapsed,
  setContextCollapsed as persistCollapsed,
} from "@/lib/sessions";
import { ChatMessage } from "@/components/ui/ChatMessage";
import { ContextPanel } from "@/components/ui/ContextPanel";
import { Sidebar } from "@/components/ui/Sidebar";
import { ModelPicker } from "@/components/ui/ModelPicker";
import { useChatStream } from "@/hooks/useChatStream";
import { useChatMessageActions } from "@/hooks/useChatMessageActions";
import { useSlashCommand } from "@/hooks/useSlashCommand";
import { ChatHeaderControls } from "@/components/chat/ChatHeaderControls";
import { ChatInputBar } from "@/components/chat/ChatInputBar";
import { ChatEmptyState } from "@/components/chat/ChatEmptyState";
import { ChatTitleEditor } from "@/components/chat/ChatTitleEditor";

export default function ChatPage() {
  const {
    active,
    activeId,
    createSession,
    addMessage,
    removeContextEntity,
    clearContextEntities,
    renameSession,
  } = useSessionStore();

  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [contextCollapsed, setCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [planMode, setPlanMode] = useState<PlanMode>("auto");
  const [searchMode, setSearchMode] = useState<SearchMode>("agent");

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef(input);
  inputRef.current = input;

  const { streamInto, isStreaming } = useChatStream();
  const { handleRetry, handlePlanConfirm, handlePlanSkip, handlePlanCancel } =
    useChatMessageActions(streamInto, { isStreaming, planMode, searchMode });
  const {
    slashCommandsAll,
    slashActiveIndex,
    setSlashActiveIndex,
    slashParsing,
    handleSlashSelect,
  } = useSlashCommand(() => inputRef.current, setInput);

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
    // One-shot prefill from upload page hand-off (asset → /teaser flow)
    try {
      const prefill = sessionStorage.getItem("bdgo.chat.prefill");
      if (prefill) {
        sessionStorage.removeItem("bdgo.chat.prefill");
        setInput(prefill);
      }
    } catch {}
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const cyclePlanMode = () => {
    const next: PlanMode = planMode === "auto" ? "on" : planMode === "on" ? "off" : "auto";
    setPlanMode(next);
    try {
      localStorage.setItem("bdgo.planMode", next);
    } catch {}
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

  const handleToggleCollapse = () => {
    const next = !contextCollapsed;
    setCollapsed(next);
    persistCollapsed(next);
  };

  const handleSend = useCallback(
    async (text?: string) => {
      const msg = (text || input).trim();
      if (!msg || isStreaming || !activeId) return;

      const currentFiles = [...attachments];
      setInput("");
      setAttachments([]);

      const userMsgId = crypto.randomUUID().slice(0, 12);
      const assistantMsgId = crypto.randomUUID().slice(0, 12);

      addMessage(activeId, {
        id: userMsgId,
        role: "user",
        content: msg,
        attachments: currentFiles.length > 0 ? currentFiles : undefined,
        createdAt: Date.now(),
      });
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
        message: msg,
        files: currentFiles,
        planModeOverride: planMode,
        searchModeOverride: searchMode,
      });
    },
    [input, isStreaming, activeId, attachments, addMessage, streamInto, planMode, searchMode],
  );

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
          <ChatTitleEditor
            title={active?.title || "New Chat"}
            onRename={(next) => activeId && renameSession(activeId, next)}
          />
          <div className="chat-header-actions">
            <ModelPicker compact />
            <ChatHeaderControls
              searchMode={searchMode}
              onSearchModeChange={(m) => {
                setSearchMode(m);
                try {
                  localStorage.setItem("bdgo.searchMode", m);
                } catch {}
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
            <ChatEmptyState onSuggestionClick={handleSend} />
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
          onRemoveAttachment={(f) => setAttachments((prev) => prev.filter((x) => x !== f))}
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

"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { chatStream, uploadBP } from "@/lib/api";
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
    markMessageDone,
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

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Hydrate client-only state
  useEffect(() => {
    setHydrated(true);
    setCollapsed(getContextCollapsed());
    // Ensure at least one session exists
    if (!activeId) {
      createSession();
    }
    // Probe for logo.png
    const probe = new Image();
    probe.onload = () => { if (probe.naturalWidth > 0) setLogoReady(true); };
    probe.src = "/logo.png";
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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

  const handleSend = useCallback(
    async (text?: string) => {
      const msg = (text || input).trim();
      if (!msg || isStreaming || !activeId) return;

      // Capture session id — locked into this closure so session switches
      // during streaming don't corrupt other sessions.
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

      setIsStreaming(true);

      try {
        const res = await chatStream(msg, targetSessionId, currentFiles);
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
                  addToolEvent(targetSessionId, assistantMsgId, {
                    type: "tool_call",
                    name: data.name,
                  });
                } else if (data.type === "tool_result") {
                  addToolEvent(targetSessionId, assistantMsgId, {
                    type: "tool_result",
                    name: data.name,
                  });
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
                  appendAssistantChunk(
                    targetSessionId,
                    assistantMsgId,
                    `\n\n**Error:** ${data.message}`,
                  );
                  markMessageDone(targetSessionId, assistantMsgId);
                } else if (data.type === "done") {
                  markMessageDone(targetSessionId, assistantMsgId);
                }
              } catch {
                /* ignore parse errors */
              }
            }
          }
        }
      } catch (e: any) {
        appendAssistantChunk(
          targetSessionId,
          assistantMsgId,
          `\n\nConnection error: ${e.message}`,
        );
        markMessageDone(targetSessionId, assistantMsgId);
      } finally {
        setIsStreaming(false);
        markMessageDone(targetSessionId, assistantMsgId);
        // Auto-title after first assistant message completes
        autoTitleFromFirstMessage(targetSessionId);
      }
    },
    [
      input,
      isStreaming,
      activeId,
      attachments,
      addMessage,
      appendAssistantChunk,
      addToolEvent,
      markMessageDone,
      addContextEntity,
    ],
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
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (input.trim() && !isStreaming) handleSend();
                  }
                }}
                placeholder={
                  attachments.length > 0
                    ? "Ask about the attached files..."
                    : "Ask anything about BD, deals, pipelines..."
                }
                disabled={isStreaming}
                rows={1}
              />
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || isStreaming}
                className="chat-send-btn"
              >
                {isStreaming ? "\u2026" : "\u2191"}
              </button>
            </div>
          </div>
        </div>
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

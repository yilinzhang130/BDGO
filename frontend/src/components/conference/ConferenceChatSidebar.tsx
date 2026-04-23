"use client";

import { useEffect, useRef, useState } from "react";
import { chatStream } from "@/lib/api";
import { parseSSEStream, type SSEEvent } from "@/lib/sseStream";

const SUGGESTED_QUESTIONS = [
  "哪些中国公司在 AACR 2026 有 CT 摘要？数据亮点是什么？",
  "AACR 2026 上 ADC 相关的最新数据有哪些？",
  "HER2/EGFR 靶点今年 AACR 的竞争格局如何？",
  "有哪些 first-in-class 靶点值得关注？",
  "ORR > 50% 的 CT 摘要都有哪些公司？",
  "和 CRM 数据对比，哪些公司在 AACR 有新进展但我们还没追踪？",
];

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  toolCalls?: string[];
}

export function ConferenceChatSidebar({
  session,
  contextHint,
  pendingAsk,
  onAskConsumed,
}: {
  session: string;
  contextHint?: string;
  pendingAsk?: string | null;
  onAskConsumed?: () => void;
}) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  // sessions.id is VARCHAR(12) in Postgres — use a 12-char UUID slice like
  // the main chat does. The previous `conference-${session}-${Date.now()}`
  // overflowed the column, so ensure_session raised mid-stream and the client
  // got a 200 OK with an empty body (→ the "未收到回复" fallback).
  const [sessionId] = useState(() => crypto.randomUUID().slice(0, 12));
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (pendingAsk && !streaming) {
      send(pendingAsk);
      onAskConsumed?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingAsk]);

  const send = async (question: string) => {
    if (!question.trim() || streaming) return;

    // Prepend conference context on first message so the LLM knows which session
    const isFirst = messages.length === 0;
    const messageToSend = isFirst
      ? `[会议上下文: ${session}${contextHint ? " | 当前视图: " + contextHint : ""}，请用 search_conference(session="${session}") 等工具查询该会议数据]\n\n${question}`
      : question;

    const userMsg: ChatMsg = { role: "user", content: question };
    const asstMsg: ChatMsg = { role: "assistant", content: "", toolCalls: [] };
    setMessages((prev) => [...prev, userMsg, asstMsg]);
    setInput("");
    setStreaming(true);

    const mutateLast = (patch: (m: ChatMsg) => ChatMsg) => {
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = patch(copy[copy.length - 1]);
        return copy;
      });
    };

    const handleEvent = (data: SSEEvent) => {
      if (data.type === "chunk") {
        mutateLast((m) => ({ ...m, content: m.content + ((data.content as string) || "") }));
      } else if (data.type === "tool_call") {
        mutateLast((m) => ({ ...m, toolCalls: [...(m.toolCalls || []), data.name as string] }));
      } else if (data.type === "error") {
        mutateLast((m) => ({ ...m, content: `❌ ${(data.message as string) || "错误"}` }));
      }
    };

    try {
      const res = await chatStream(messageToSend, sessionId, [], undefined, "off");
      await parseSSEStream(res, handleEvent);
    } catch (e: unknown) {
      mutateLast((m) => ({ ...m, content: `❌ ${(e as Error)?.message || "连接失败，请重试"}` }));
    } finally {
      setStreaming(false);
      // Fallback if assistant message ended up empty (no chunks received)
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && !last.content) {
          const copy = [...prev];
          copy[copy.length - 1] = { ...last, content: "❌ 未收到回复，请重试" };
          return copy;
        }
        return prev;
      });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send(input);
  };

  return (
    <div
      style={{
        width: 340,
        flexShrink: 0,
        borderLeft: "1px solid #e5e7eb",
        background: "#fafafa",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
      }}
    >
      <div style={{ padding: "14px 16px", borderBottom: "1px solid #e5e7eb", background: "#fff" }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 700,
            color: "#111827",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          💬 对话分析
          {streaming && (
            <span style={{ fontSize: 10, color: "#2563eb", fontWeight: 500 }}>思考中…</span>
          )}
        </div>
        <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>
          基于 {session} 数据 ·{" "}
          {messages.length > 0 ? `${Math.ceil(messages.length / 2)} 轮对话` : "直接提问"}
        </div>
      </div>

      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "12px 12px" }}>
        {messages.length === 0 ? (
          <>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#6b7280",
                marginBottom: 8,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              试试这些问题
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {SUGGESTED_QUESTIONS.map((q, i) => (
                <button
                  key={i}
                  onClick={() => send(q)}
                  disabled={streaming}
                  style={{
                    textAlign: "left",
                    padding: "10px 12px",
                    borderRadius: 8,
                    background: "#fff",
                    border: "1px solid #e5e7eb",
                    fontSize: 12,
                    color: "#374151",
                    lineHeight: 1.5,
                    cursor: streaming ? "not-allowed" : "pointer",
                    transition: "border-color 0.1s, box-shadow 0.1s",
                  }}
                  onMouseEnter={(e) => {
                    if (!streaming) {
                      (e.currentTarget as HTMLElement).style.borderColor = "#93c5fd";
                      (e.currentTarget as HTMLElement).style.boxShadow =
                        "0 2px 8px rgba(0,0,0,0.06)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.borderColor = "#e5e7eb";
                    (e.currentTarget as HTMLElement).style.boxShadow = "none";
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {messages.map((m, i) => (
              <div
                key={i}
                style={{
                  alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "92%",
                }}
              >
                {m.role === "user" ? (
                  <div
                    style={{
                      background: "#1e3a8a",
                      color: "#fff",
                      padding: "8px 12px",
                      borderRadius: 12,
                      fontSize: 13,
                      lineHeight: 1.5,
                      borderBottomRightRadius: 4,
                    }}
                  >
                    {m.content}
                  </div>
                ) : (
                  <div>
                    {m.toolCalls && m.toolCalls.length > 0 && (
                      <div
                        style={{
                          fontSize: 10,
                          color: "#9ca3af",
                          marginBottom: 4,
                          fontStyle: "italic",
                        }}
                      >
                        🔍 {m.toolCalls.map((t) => `调用 ${t}`).join(" · ")}
                      </div>
                    )}
                    <div
                      style={{
                        background: "#fff",
                        color: "#111827",
                        padding: "10px 13px",
                        borderRadius: 12,
                        fontSize: 13,
                        lineHeight: 1.65,
                        border: "1px solid #e5e7eb",
                        borderBottomLeftRadius: 4,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                      }}
                    >
                      {m.content || (streaming && i === messages.length - 1 ? "…" : "")}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        style={{
          padding: "10px 12px",
          borderTop: "1px solid #e5e7eb",
          background: "#fff",
          display: "flex",
          gap: 6,
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={streaming ? "等待回复…" : "问任何问题…"}
          disabled={streaming}
          style={{
            flex: 1,
            padding: "8px 12px",
            border: "1px solid #d1d5db",
            borderRadius: 8,
            fontSize: 13,
            color: "#374151",
            outline: "none",
          }}
        />
        <button
          type="submit"
          disabled={!input.trim() || streaming}
          style={{
            padding: "8px 14px",
            background: input.trim() && !streaming ? "#1e3a8a" : "#d1d5db",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 600,
            cursor: input.trim() && !streaming ? "pointer" : "not-allowed",
          }}
        >
          发送
        </button>
      </form>

      {messages.length > 0 && (
        <button
          onClick={() => setMessages([])}
          style={{
            padding: "6px",
            background: "transparent",
            border: "none",
            borderTop: "1px solid #f3f4f6",
            fontSize: 11,
            color: "#9ca3af",
            cursor: "pointer",
          }}
        >
          清空对话
        </button>
      )}
    </div>
  );
}

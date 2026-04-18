"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  fetchConferenceSessions,
  fetchConferenceStats,
  fetchConferenceCompanies,
  fetchConferenceAbstracts,
  chatStream,
  ConferenceSession,
  ConferenceCompanyCard,
  ConferenceAbstract,
} from "@/lib/api";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function cleanTitle(title: string): string {
  return title.replace(/^Abstract [A-Z0-9]+:\s*/i, "").replace(/^Abstract:\s*/i, "");
}

// ─── Badges ───────────────────────────────────────────────────────────────────

const KIND_CFG: Record<string, { bg: string; color: string; border: string }> = {
  CT:      { bg: "#fef2f2", color: "#dc2626", border: "#fca5a5" },
  LB:      { bg: "#fff7ed", color: "#c2410c", border: "#fdba74" },
  regular: { bg: "#f3f4f6", color: "#4b5563", border: "#d1d5db" },
};

function KindBadge({ kind }: { kind: string }) {
  const cfg = KIND_CFG[kind] || KIND_CFG.regular;
  const label = kind === "regular" ? "Poster" : kind;
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, padding: "2px 7px", borderRadius: 5,
      background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}`,
      letterSpacing: "0.03em", flexShrink: 0,
    }}>{label}</span>
  );
}

const TYPE_CFG: Record<string, { bg: string; color: string }> = {
  "Biotech":     { bg: "#eff6ff", color: "#1d4ed8" },
  "Biotech(CN)": { bg: "#f0fdf4", color: "#166534" },
  "Biotech(US)": { bg: "#eff6ff", color: "#1d4ed8" },
  "Biotech(EU)": { bg: "#faf5ff", color: "#6b21a8" },
  "Pharma":      { bg: "#fff7ed", color: "#9a3412" },
  "Pharma(CN)":  { bg: "#f0fdf4", color: "#166534" },
  "MNC":         { bg: "#fefce8", color: "#854d0e" },
};

function TypeBadge({ type }: { type?: string }) {
  if (!type) return null;
  const cfg = TYPE_CFG[type] || { bg: "#f3f4f6", color: "#6b7280" };
  return (
    <span style={{
      fontSize: 11, fontWeight: 600, padding: "1px 6px", borderRadius: 5,
      background: cfg.bg, color: cfg.color,
    }}>{type}</span>
  );
}

function TargetTag({ label }: { label: string }) {
  return (
    <span style={{
      fontSize: 11, padding: "2px 7px", borderRadius: 20,
      background: "#dbeafe", color: "#1e40af", fontWeight: 600,
    }}>{label}</span>
  );
}

function DataTag({ label, value }: { label: string; value: string }) {
  return (
    <span style={{
      fontSize: 11, padding: "2px 7px", borderRadius: 20,
      background: "#f0fdf4", color: "#166534", fontWeight: 500,
    }}>{label}: <strong>{value}</strong></span>
  );
}

// ─── Abstract card ─────────────────────────────────────────────────────────────

function AbstractCard({ ab, onClick }: { ab: ConferenceAbstract; onClick: () => void }) {
  const importantDp = Object.entries(ab.data_points || {}).filter(
    ([k]) => ["ORR", "DOR", "mDOR", "mPFS", "mOS", "DCR", "N", "Gr3+AE"].includes(k)
  );

  return (
    <div
      onClick={onClick}
      style={{
        background: "#fff", border: "1px solid #e5e7eb", borderRadius: 12,
        padding: "18px 20px", cursor: "pointer", transition: "box-shadow 0.15s, border-color 0.15s",
        display: "flex", flexDirection: "column", gap: 10,
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 20px rgba(0,0,0,0.08)";
        (e.currentTarget as HTMLElement).style.borderColor = "#93c5fd";
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.boxShadow = "none";
        (e.currentTarget as HTMLElement).style.borderColor = "#e5e7eb";
      }}
    >
      {/* Kind + title */}
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
        <KindBadge kind={ab.kind} />
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "#111827", lineHeight: 1.45, flex: 1 }}>
          {cleanTitle(ab.title)}
        </h3>
      </div>

      {/* Company */}
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "#374151", fontWeight: 600 }}>{ab.company}</span>
        <TypeBadge type={ab.客户类型} />
        {ab.所处国家 && (
          <span style={{ fontSize: 12, color: "#9ca3af" }}>· {ab.所处国家}</span>
        )}
      </div>

      {/* Targets */}
      {ab.targets?.length > 0 && (
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
          {ab.targets.slice(0, 6).map(t => <TargetTag key={t} label={t} />)}
        </div>
      )}

      {/* Data points */}
      {importantDp.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {importantDp.map(([k, v]) => <DataTag key={k} label={k} value={v} />)}
        </div>
      )}

      {/* Conclusion = Key Points */}
      {ab.conclusion && (
        <div style={{
          background: "#f9fafb", borderRadius: 8, padding: "10px 12px",
          fontSize: 12, color: "#374151", lineHeight: 1.6,
        }}>
          <div style={{ fontWeight: 600, fontSize: 11, color: "#6b7280", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Key Finding
          </div>
          {ab.conclusion}
        </div>
      )}

      {/* NCT + DOI */}
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        {ab.ncts?.map(nct => (
          <a key={nct} href={`https://clinicaltrials.gov/study/${nct}`} target="_blank" rel="noopener noreferrer"
            style={{ fontSize: 11, color: "#2563eb" }} onClick={e => e.stopPropagation()}>
            {nct} ↗
          </a>
        ))}
        {ab.doi && (
          <a href={`https://doi.org/${ab.doi}`} target="_blank" rel="noopener noreferrer"
            style={{ fontSize: 11, color: "#9ca3af", marginLeft: "auto" }} onClick={e => e.stopPropagation()}>
            Abstract ↗
          </a>
        )}
      </div>
    </div>
  );
}

// ─── Company card (compact) ────────────────────────────────────────────────────

function CompanyCard({ card, onClick }: { card: ConferenceCompanyCard; onClick: () => void }) {
  const hotCount = card.CT_count + card.LB_count;
  const uniqueTargets = Array.from(new Set(card.top_abstracts.flatMap(a => a.targets || []))).slice(0, 5);

  return (
    <div
      onClick={onClick}
      style={{
        background: "#fff", border: "1px solid #e5e7eb", borderRadius: 12,
        padding: "16px 18px", cursor: "pointer", transition: "box-shadow 0.15s, border-color 0.15s",
        display: "flex", flexDirection: "column", gap: 10,
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 20px rgba(0,0,0,0.08)";
        (e.currentTarget as HTMLElement).style.borderColor = "#93c5fd";
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.boxShadow = "none";
        (e.currentTarget as HTMLElement).style.borderColor = "#e5e7eb";
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "flex-start" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: "#111827", marginBottom: 5 }}>{card.company}</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <TypeBadge type={card.客户类型} />
            {card.所处国家 && <span style={{ fontSize: 11, color: "#9ca3af" }}>{card.所处国家}</span>}
            {card.Ticker && <span style={{ fontSize: 11, color: "#d1d5db" }}>· {card.Ticker}</span>}
          </div>
        </div>
        {hotCount > 0 && (
          <div style={{
            flexShrink: 0, textAlign: "center", background: "#fef2f2",
            borderRadius: 8, padding: "5px 10px", border: "1px solid #fca5a5",
          }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: "#dc2626", lineHeight: 1 }}>{hotCount}</div>
            <div style={{ fontSize: 9, color: "#dc2626", fontWeight: 700 }}>CT/LB</div>
          </div>
        )}
      </div>

      {/* Stats */}
      <div style={{ display: "flex", gap: 14, fontSize: 12 }}>
        {card.CT_count > 0 && <span style={{ color: "#dc2626" }}><strong>{card.CT_count}</strong> CT</span>}
        {card.LB_count > 0 && <span style={{ color: "#d97706" }}><strong>{card.LB_count}</strong> LB</span>}
        <span style={{ color: "#6b7280" }}><strong>{card.abstract_count}</strong> 摘要</span>
      </div>

      {/* Top abstract titles */}
      {card.top_abstracts.slice(0, 2).map((ab, i) => (
        <div key={i} style={{ fontSize: 12, color: "#4b5563", lineHeight: 1.4, display: "flex", gap: 5 }}>
          <KindBadge kind={ab.kind} />
          <span style={{ flex: 1,
            overflow: "hidden", display: "-webkit-box",
            WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
          }}>{cleanTitle(ab.title)}</span>
        </div>
      ))}

      {/* Targets */}
      {uniqueTargets.length > 0 && (
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {uniqueTargets.map(t => <TargetTag key={t} label={t} />)}
        </div>
      )}
    </div>
  );
}

// ─── Inline streaming chat sidebar ────────────────────────────────────────────

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
  toolCalls?: string[];  // names of tools the LLM invoked
}

function ChatSidebar({
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
  const [sessionId] = useState(() => `conference-${session}-${Date.now()}`);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new content arrives
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  // External question injection (from detail modal)
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
    setMessages(prev => [...prev, userMsg, asstMsg]);
    setInput("");
    setStreaming(true);

    try {
      const res = await chatStream(messageToSend, sessionId, [], undefined, "off");
      const reader = res.body?.getReader();
      if (!reader) throw new Error("no stream");
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        while (buffer.includes("\n\n")) {
          const end = buffer.indexOf("\n\n");
          const eventText = buffer.slice(0, end);
          buffer = buffer.slice(end + 2);

          for (const line of eventText.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "chunk") {
                setMessages(prev => {
                  const copy = [...prev];
                  copy[copy.length - 1] = {
                    ...copy[copy.length - 1],
                    content: copy[copy.length - 1].content + (data.content || ""),
                  };
                  return copy;
                });
              } else if (data.type === "tool_call") {
                setMessages(prev => {
                  const copy = [...prev];
                  const last = copy[copy.length - 1];
                  copy[copy.length - 1] = {
                    ...last,
                    toolCalls: [...(last.toolCalls || []), data.name],
                  };
                  return copy;
                });
              } else if (data.type === "error") {
                setMessages(prev => {
                  const copy = [...prev];
                  copy[copy.length - 1] = {
                    ...copy[copy.length - 1],
                    content: `❌ ${data.message || "错误"}`,
                  };
                  return copy;
                });
              }
            } catch { /* ignore */ }
          }
        }
      }
    } catch (e: any) {
      setMessages(prev => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          ...copy[copy.length - 1],
          content: `❌ ${e?.message || "连接失败"}`,
        };
        return copy;
      });
    } finally {
      setStreaming(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send(input);
  };

  return (
    <div style={{
      width: 340, flexShrink: 0, borderLeft: "1px solid #e5e7eb",
      background: "#fafafa", display: "flex", flexDirection: "column",
      height: "100%", overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{ padding: "14px 16px", borderBottom: "1px solid #e5e7eb", background: "#fff" }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "#111827", display: "flex", alignItems: "center", gap: 6 }}>
          💬 对话分析
          {streaming && <span style={{ fontSize: 10, color: "#2563eb", fontWeight: 500 }}>思考中…</span>}
        </div>
        <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>
          基于 {session} 数据 · {messages.length > 0 ? `${Math.ceil(messages.length / 2)} 轮对话` : "直接提问"}
        </div>
      </div>

      {/* Scroll area */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "12px 12px" }}>
        {messages.length === 0 ? (
          // Suggested questions (only when empty)
          <>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#6b7280", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              试试这些问题
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {SUGGESTED_QUESTIONS.map((q, i) => (
                <button
                  key={i}
                  onClick={() => send(q)}
                  disabled={streaming}
                  style={{
                    textAlign: "left", padding: "10px 12px", borderRadius: 8,
                    background: "#fff", border: "1px solid #e5e7eb", fontSize: 12,
                    color: "#374151", lineHeight: 1.5, cursor: streaming ? "not-allowed" : "pointer",
                    transition: "border-color 0.1s, box-shadow 0.1s",
                  }}
                  onMouseEnter={e => {
                    if (!streaming) {
                      (e.currentTarget as HTMLElement).style.borderColor = "#93c5fd";
                      (e.currentTarget as HTMLElement).style.boxShadow = "0 2px 8px rgba(0,0,0,0.06)";
                    }
                  }}
                  onMouseLeave={e => {
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
          // Message list
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {messages.map((m, i) => (
              <div key={i} style={{
                alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                maxWidth: "92%",
              }}>
                {m.role === "user" ? (
                  <div style={{
                    background: "#1e3a8a", color: "#fff", padding: "8px 12px",
                    borderRadius: 12, fontSize: 13, lineHeight: 1.5,
                    borderBottomRightRadius: 4,
                  }}>{m.content}</div>
                ) : (
                  <div>
                    {m.toolCalls && m.toolCalls.length > 0 && (
                      <div style={{ fontSize: 10, color: "#9ca3af", marginBottom: 4, fontStyle: "italic" }}>
                        🔍 {m.toolCalls.map(t => `调用 ${t}`).join(" · ")}
                      </div>
                    )}
                    <div style={{
                      background: "#fff", color: "#111827", padding: "10px 13px",
                      borderRadius: 12, fontSize: 13, lineHeight: 1.65,
                      border: "1px solid #e5e7eb", borderBottomLeftRadius: 4,
                      whiteSpace: "pre-wrap", wordBreak: "break-word",
                    }}>
                      {m.content || (streaming && i === messages.length - 1 ? "…" : "")}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} style={{
        padding: "10px 12px", borderTop: "1px solid #e5e7eb", background: "#fff",
        display: "flex", gap: 6,
      }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={streaming ? "等待回复…" : "问任何问题…"}
          disabled={streaming}
          style={{
            flex: 1, padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: 8,
            fontSize: 13, color: "#374151", outline: "none",
          }}
        />
        <button
          type="submit"
          disabled={!input.trim() || streaming}
          style={{
            padding: "8px 14px", background: input.trim() && !streaming ? "#1e3a8a" : "#d1d5db",
            color: "#fff", border: "none", borderRadius: 8, fontSize: 13,
            fontWeight: 600, cursor: input.trim() && !streaming ? "pointer" : "not-allowed",
          }}
        >发送</button>
      </form>

      {messages.length > 0 && (
        <button
          onClick={() => setMessages([])}
          style={{
            padding: "6px", background: "transparent", border: "none",
            borderTop: "1px solid #f3f4f6", fontSize: 11, color: "#9ca3af",
            cursor: "pointer",
          }}
        >清空对话</button>
      )}
    </div>
  );
}

// ─── Abstract detail panel ────────────────────────────────────────────────────

function AbstractDetailPanel({
  ab,
  onClose,
  onAsk,
}: {
  ab: ConferenceAbstract | null;
  onClose: () => void;
  onAsk: (question: string) => void;
}) {
  if (!ab) return null;

  const importantDp = Object.entries(ab.data_points || {});

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)",
      zIndex: 1000, display: "flex", alignItems: "flex-start", justifyContent: "center",
      padding: "48px 16px", overflowY: "auto",
    }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: "#fff", borderRadius: 16, width: "100%", maxWidth: 680,
        padding: "28px 32px", position: "relative",
      }}>
        <button onClick={onClose} style={{
          position: "absolute", top: 14, right: 14, border: "none",
          background: "#f3f4f6", borderRadius: 6, width: 28, height: 28,
          cursor: "pointer", fontSize: 16, lineHeight: "28px", color: "#6b7280",
        }}>×</button>

        {/* Kind + title */}
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start", marginBottom: 12 }}>
          <KindBadge kind={ab.kind} />
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "#111827", lineHeight: 1.4, flex: 1 }}>
            {cleanTitle(ab.title)}
          </h2>
        </div>

        {/* Company */}
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16, flexWrap: "wrap" }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#374151" }}>{ab.company}</span>
          <TypeBadge type={ab.客户类型} />
          <span style={{ fontSize: 13, color: "#9ca3af" }}>{ab.所处国家}</span>
        </div>

        {/* Targets */}
        {ab.targets?.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#6b7280", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>靶点</div>
            <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
              {ab.targets.map(t => <TargetTag key={t} label={t} />)}
            </div>
          </div>
        )}

        {/* Data points */}
        {importantDp.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#6b7280", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>临床数据</div>
            <div style={{
              display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))",
              gap: 8,
            }}>
              {importantDp.map(([k, v]) => (
                <div key={k} style={{
                  background: "#f9fafb", borderRadius: 8, padding: "10px 12px",
                  border: "1px solid #e5e7eb",
                }}>
                  <div style={{ fontSize: 11, color: "#9ca3af", marginBottom: 2 }}>{k}</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: "#111827" }}>{v}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Key Finding */}
        {ab.conclusion && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#6b7280", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>Key Finding</div>
            <div style={{
              background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 10,
              padding: "14px 16px", fontSize: 13, color: "#14532d", lineHeight: 1.7,
            }}>
              {ab.conclusion}
            </div>
          </div>
        )}

        {/* Links */}
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 4 }}>
          {ab.ncts?.map(nct => (
            <a key={nct} href={`https://clinicaltrials.gov/study/${nct}`} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 13, color: "#2563eb", fontWeight: 500 }}>
              {nct} ↗
            </a>
          ))}
          {ab.doi && (
            <a href={`https://doi.org/${ab.doi}`} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 13, color: "#6b7280" }}>
              原文摘要 ↗
            </a>
          )}
        </div>

        {/* Chat with this abstract */}
        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid #f3f4f6" }}>
          <button
            onClick={() => {
              onAsk(`深度分析 ${ab.company} 的摘要《${cleanTitle(ab.title).slice(0, 60)}》，结合CRM数据给出BD评估`);
              onClose();
            }}
            style={{
              padding: "9px 20px", background: "#1e3a8a", color: "#fff", border: "none",
              borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer",
            }}
          >
            💬 让右侧AI分析这条摘要
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────

type ViewMode = "abstracts" | "companies";

export default function ConferencePage() {
  const [sessions, setSessions] = useState<ConferenceSession[]>([]);
  const [activeSession, setActiveSession] = useState("AACR-2026");
  const [stats, setStats] = useState<any>(null);
  const [view, setView] = useState<ViewMode>("abstracts");

  // Shared filters
  const [q, setQ] = useState("");
  const [companyType, setCompanyType] = useState("");
  const [country, setCountry] = useState("");
  const [kind, setKind] = useState("");
  const [page, setPage] = useState(1);

  // Abstract view
  const [abstracts, setAbstracts] = useState<any>(null);
  const [loadingAbs, setLoadingAbs] = useState(false);

  // Company view
  const [companies, setCompanies] = useState<any>(null);
  const [loadingCo, setLoadingCo] = useState(false);

  // Detail
  const [selectedAb, setSelectedAb] = useState<ConferenceAbstract | null>(null);

  // Pending question to feed into the inline chat (from detail modal)
  const [pendingAsk, setPendingAsk] = useState<string | null>(null);

  // Load sessions
  useEffect(() => {
    fetchConferenceSessions()
      .then(r => setSessions(r.sessions))
      .catch(() => {});
  }, []);

  // Load stats
  useEffect(() => {
    fetchConferenceStats(activeSession).then(setStats).catch(() => setStats(null));
  }, [activeSession]);

  // Load abstracts
  const loadAbstracts = useCallback(() => {
    setLoadingAbs(true);
    fetchConferenceAbstracts(activeSession, { q, company_type: companyType, country, kind, page })
      .then(d => { setAbstracts(d); setLoadingAbs(false); })
      .catch(() => setLoadingAbs(false));
  }, [activeSession, q, companyType, country, kind, page]);

  // Load companies
  const loadCompanies = useCallback(() => {
    setLoadingCo(true);
    fetchConferenceCompanies(activeSession, {
      q, company_type: companyType, country, ct_only: kind === "CT",
      page, page_size: 24,
    })
      .then(d => { setCompanies(d); setLoadingCo(false); })
      .catch(() => setLoadingCo(false));
  }, [activeSession, q, companyType, country, kind, page]);

  useEffect(() => {
    if (view === "abstracts") loadAbstracts();
    else loadCompanies();
  }, [view, loadAbstracts, loadCompanies]);

  // Reset page on filter change
  useEffect(() => { setPage(1); }, [activeSession, q, companyType, country, kind, view]);

  const activeSessionMeta = sessions.find(s => s.id === activeSession);
  const facets = view === "abstracts" ? abstracts?.facets : companies?.facets;
  const currentData = view === "abstracts" ? abstracts : companies;
  const isLoading = view === "abstracts" ? loadingAbs : loadingCo;
  const totalItems = currentData?.total ?? 0;

  return (
    <div style={{ display: "flex", height: "100vh", background: "#f8fafc", overflow: "hidden" }}>

      {/* Main content */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Header */}
        <div style={{
          background: "#fff", borderBottom: "1px solid #e5e7eb",
          padding: "14px 24px", flexShrink: 0,
        }}>
          {/* Row 1: title + session selector + chat */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
            <div style={{ flex: 1 }}>
              <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "#111827" }}>
                {activeSessionMeta?.full_name || activeSession}
              </h1>
              {activeSessionMeta?.location && (
                <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 1 }}>{activeSessionMeta.location}</div>
              )}
            </div>

            {sessions.length > 1 && (
              <select
                value={activeSession}
                onChange={e => setActiveSession(e.target.value)}
                style={{ fontSize: 13, padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 7, color: "#374151" }}
              >
                {sessions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            )}
          </div>

          {/* Stats bar */}
          {stats && (
            <div style={{ display: "flex", gap: 20, marginBottom: 12, flexWrap: "wrap" }}>
              <StatChip icon="🏢" label="BD公司" value={stats.total_companies ?? stats.total_bd_heat_companies} color="#1d4ed8" />
              <StatChip icon="🔴" label="CT摘要" value={stats.total_ct} color="#dc2626" />
              <StatChip icon="🟠" label="Late-Breaking" value={stats.total_lb} color="#d97706" />
              <StatChip icon="🇨🇳" label="中国公司" value={stats.by_country?.["中国"]} color="#166534" />
            </div>
          )}

          {/* View toggle + Filters */}
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            {/* View toggle */}
            <div style={{
              display: "flex", border: "1px solid #d1d5db", borderRadius: 8, overflow: "hidden",
              flexShrink: 0,
            }}>
              {([["abstracts", "摘要卡片"], ["companies", "公司视图"]] as const).map(([v, label]) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  style={{
                    padding: "6px 14px", fontSize: 12, fontWeight: 600, border: "none",
                    background: view === v ? "#1e3a8a" : "#fff",
                    color: view === v ? "#fff" : "#6b7280",
                    cursor: "pointer", transition: "all 0.1s",
                  }}
                >{label}</button>
              ))}
            </div>

            {/* Search */}
            <input
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder={view === "abstracts" ? "搜索标题/靶点/公司…" : "搜索公司名称…"}
              style={{
                padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 7,
                fontSize: 13, color: "#374151", width: 200,
              }}
            />

            {/* Type filter */}
            <select value={companyType} onChange={e => setCompanyType(e.target.value)}
              style={{ fontSize: 13, padding: "6px 9px", border: "1px solid #d1d5db", borderRadius: 7, color: "#374151" }}>
              <option value="">所有类型</option>
              {(facets?.types || []).map((t: string) => <option key={t} value={t}>{t}</option>)}
            </select>

            {/* Country filter */}
            <select value={country} onChange={e => setCountry(e.target.value)}
              style={{ fontSize: 13, padding: "6px 9px", border: "1px solid #d1d5db", borderRadius: 7, color: "#374151" }}>
              <option value="">所有国家</option>
              {(facets?.countries || []).map((c: string) => <option key={c} value={c}>{c}</option>)}
            </select>

            {/* Kind filter (abstracts only) */}
            {view === "abstracts" && (
              <select value={kind} onChange={e => setKind(e.target.value)}
                style={{ fontSize: 13, padding: "6px 9px", border: "1px solid #d1d5db", borderRadius: 7, color: "#374151" }}>
                <option value="">全部类型</option>
                <option value="CT">Clinical Trial (CT)</option>
                <option value="LB">Late-Breaking (LB)</option>
                <option value="regular">Poster</option>
              </select>
            )}

            {/* Reset */}
            {(q || companyType || country || kind) && (
              <button
                onClick={() => { setQ(""); setCompanyType(""); setCountry(""); setKind(""); }}
                style={{ fontSize: 12, padding: "5px 10px", border: "1px solid #d1d5db", borderRadius: 6, background: "#f9fafb", cursor: "pointer", color: "#6b7280" }}
              >重置</button>
            )}

            {/* Count */}
            <span style={{ marginLeft: "auto", fontSize: 12, color: "#9ca3af" }}>
              {totalItems > 0 ? `${totalItems} 条` : ""}
            </span>
          </div>
        </div>

        {/* Content area */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
          {isLoading ? (
            <div style={{ textAlign: "center", padding: "80px 0", color: "#9ca3af", fontSize: 14 }}>加载中…</div>
          ) : totalItems === 0 ? (
            <div style={{ textAlign: "center", padding: "80px 0", color: "#9ca3af" }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>🔍</div>
              <div style={{ fontSize: 14 }}>没有找到匹配数据</div>
            </div>
          ) : (
            <>
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
                gap: 14,
              }}>
                {view === "abstracts"
                  ? (abstracts?.data || []).map((ab: ConferenceAbstract, i: number) => (
                    <AbstractCard key={i} ab={ab} onClick={() => setSelectedAb(ab)} />
                  ))
                  : (companies?.data || []).map((card: ConferenceCompanyCard, i: number) => (
                    <CompanyCard key={i} card={card} onClick={() => {
                      // Switch to abstracts view filtered by this company
                      setQ(card.company); setView("abstracts");
                    }} />
                  ))
                }
              </div>

              {/* Pagination */}
              {currentData && currentData.total_pages > 1 && (
                <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 28, alignItems: "center" }}>
                  <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
                    style={{
                      padding: "7px 16px", border: "1px solid #d1d5db", borderRadius: 7,
                      background: page <= 1 ? "#f9fafb" : "#fff", cursor: page <= 1 ? "not-allowed" : "pointer",
                      fontSize: 13, color: page <= 1 ? "#d1d5db" : "#374151",
                    }}>← 上一页</button>
                  <span style={{ fontSize: 13, color: "#6b7280" }}>{page} / {currentData.total_pages}</span>
                  <button disabled={page >= currentData.total_pages} onClick={() => setPage(p => p + 1)}
                    style={{
                      padding: "7px 16px", border: "1px solid #d1d5db", borderRadius: 7,
                      background: page >= currentData.total_pages ? "#f9fafb" : "#fff",
                      cursor: page >= currentData.total_pages ? "not-allowed" : "pointer",
                      fontSize: 13, color: page >= currentData.total_pages ? "#d1d5db" : "#374151",
                    }}>下一页 →</button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Chat sidebar */}
      <ChatSidebar
        session={activeSession}
        contextHint={view === "abstracts" ? `摘要视图${kind ? "-" + kind : ""}${country ? "-" + country : ""}` : "公司视图"}
        pendingAsk={pendingAsk}
        onAskConsumed={() => setPendingAsk(null)}
      />

      {/* Abstract detail modal */}
      {selectedAb && (
        <AbstractDetailPanel
          ab={selectedAb}
          onClose={() => setSelectedAb(null)}
          onAsk={(q) => setPendingAsk(q)}
        />
      )}
    </div>
  );
}

// ─── Stat chip ─────────────────────────────────────────────────────────────────

function StatChip({ icon, label, value, color }: { icon: string; label: string; value?: number; color: string }) {
  if (value == null || value === 0) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
      <span style={{ fontSize: 14 }}>{icon}</span>
      <span style={{ fontSize: 20, fontWeight: 800, color }}>{value.toLocaleString()}</span>
      <span style={{ fontSize: 12, color: "#6b7280" }}>{label}</span>
    </div>
  );
}

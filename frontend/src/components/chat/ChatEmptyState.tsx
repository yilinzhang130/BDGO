"use client";

const SUGGESTIONS = [
  "AbbVie有几个 Phase 3 的资产？",
  "帮我分析一下 Biogen 的管线",
  "近期最大的 BD 交易是哪个？",
  "按阶段统计资产数量",
];

const SLASH_EXAMPLES: { alias: string; label: string; hint: string }[] = [
  { alias: "/mnc ", label: "/mnc", hint: "MNC买方画像" },
  { alias: "/dd ", label: "/dd", hint: "尽调清单" },
  { alias: "/evaluate ", label: "/evaluate", hint: "资产交易吸引力" },
  { alias: "/buyers ", label: "/buyers", hint: "反向买方匹配" },
  { alias: "/email ", label: "/email", hint: "BD外联邮件" },
  { alias: "/disease ", label: "/disease", hint: "疾病竞争格局" },
];

export function ChatEmptyState({
  onSuggestionClick,
  onCommandPrefill,
}: {
  onSuggestionClick: (text: string) => void;
  onCommandPrefill?: (text: string) => void;
}) {
  return (
    <div className="chat-empty">
      <h1 className="chat-title">
        <span className="brand-bd">BD</span>
        <span className="brand-go"> Go</span>
      </h1>
      <p className="chat-subtitle">Biotech BD Intelligence Assistant</p>
      <div className="chat-suggestions">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="chat-suggestion" onClick={() => onSuggestionClick(s)}>
            {s}
          </button>
        ))}
      </div>

      <div style={{ marginTop: "1.5rem", textAlign: "center" }}>
        <p
          style={{
            fontSize: "0.75rem",
            color: "var(--text-muted)",
            marginBottom: "0.6rem",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          报告指令 — 输入 / 触发
        </p>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "0.4rem",
            justifyContent: "center",
            maxWidth: 480,
            margin: "0 auto",
          }}
        >
          {SLASH_EXAMPLES.map(({ alias, label, hint }) => (
            <button
              key={alias}
              onClick={() => onCommandPrefill?.(alias)}
              title={hint}
              style={{
                padding: "4px 10px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "var(--bg-subtle)",
                color: "var(--accent)",
                fontSize: "0.78rem",
                fontFamily: "var(--font-mono, monospace)",
                fontWeight: 600,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                transition: "background 0.12s, border-color 0.12s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-active)";
                e.currentTarget.style.borderColor = "var(--accent)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "var(--bg-subtle)";
                e.currentTarget.style.borderColor = "var(--border)";
              }}
            >
              {label}
              <span
                style={{
                  fontSize: "0.7rem",
                  color: "var(--text-muted)",
                  fontFamily: "inherit",
                  fontWeight: 400,
                }}
              >
                {hint}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

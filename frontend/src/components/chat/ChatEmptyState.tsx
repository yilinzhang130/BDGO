"use client";

const SUGGESTIONS = [
  "AbbVie\u6709\u51E0\u4E2A Phase 3 \u7684\u8D44\u4EA7\uFF1F",
  "\u5E2E\u6211\u5206\u6790\u4E00\u4E0B Biogen \u7684\u7BA1\u7EBF",
  "\u8FD1\u671F\u6700\u5927\u7684 BD \u4EA4\u6613\u662F\u54EA\u4E2A\uFF1F",
  "\u6309\u9636\u6BB5\u7EDF\u8BA1\u8D44\u4EA7\u6570\u91CF",
];

/** Title + suggested questions shown when the chat has no messages. */
export function ChatEmptyState({
  onSuggestionClick,
}: {
  onSuggestionClick: (text: string) => void;
}) {
  return (
    <div className="chat-empty">
      <p
        style={{
          fontSize: 12,
          color: "var(--text-muted)",
          margin: "0 0 1.25rem",
          letterSpacing: "0.01em",
        }}
      >
        📋 也试试 Watchlist · 📊 Outreach（敬请期待）
      </p>
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
    </div>
  );
}

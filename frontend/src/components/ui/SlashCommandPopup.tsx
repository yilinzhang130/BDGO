"use client";

// Slash-command autocomplete popup for the chat input.
// Shown when the textarea content starts with "/". Filters the 8 report
// services by alias/name. Keyboard nav is driven by the parent (chat page)
// because it owns the textarea.

export interface SlashCommand {
  alias: string;          // e.g. "mnc" — what the user types after "/"
  slug: string;           // canonical report service slug
  displayName: string;    // e.g. "MNC Buyer Profile"
  description: string;
  estimatedSeconds?: number;
}

// Canonical alias → slug map. Kept in frontend because the short names are
// UX decisions, not part of the backend contract.
export const SLASH_COMMANDS: Omit<SlashCommand, "displayName" | "description" | "estimatedSeconds">[] = [
  { alias: "paper", slug: "paper-analysis" },
  { alias: "mnc", slug: "buyer-profile" },
  { alias: "dd", slug: "dd-checklist" },
  { alias: "commercial", slug: "commercial-assessment" },
  { alias: "disease", slug: "disease-landscape" },
  { alias: "target", slug: "target-radar" },
  { alias: "ip", slug: "ip-landscape" },
  { alias: "guidelines", slug: "clinical-guidelines" },
];

export function filterCommands(commands: SlashCommand[], query: string): SlashCommand[] {
  const q = query.trim().toLowerCase();
  if (!q) return commands;
  return commands.filter(
    (c) =>
      c.alias.toLowerCase().startsWith(q) ||
      c.slug.toLowerCase().includes(q) ||
      c.displayName.toLowerCase().includes(q),
  );
}

interface Props {
  commands: SlashCommand[];
  activeIndex: number;
  onSelect: (cmd: SlashCommand) => void;
  onHover: (index: number) => void;
}

export function SlashCommandPopup({ commands, activeIndex, onSelect, onHover }: Props) {
  if (commands.length === 0) {
    return (
      <div style={popupStyle}>
        <div style={{ padding: "12px 14px", fontSize: 13, color: "var(--text-muted)" }}>
          No matching command
        </div>
      </div>
    );
  }

  return (
    <div style={popupStyle} role="listbox">
      <div
        style={{
          padding: "6px 12px",
          fontSize: 11,
          color: "var(--text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          borderBottom: "1px solid var(--border-light)",
        }}
      >
        Report commands · ↑↓ navigate · ↵ select · esc dismiss
      </div>
      {commands.map((cmd, i) => {
        const active = i === activeIndex;
        return (
          <div
            key={cmd.alias}
            role="option"
            aria-selected={active}
            onMouseDown={(e) => {
              e.preventDefault();
              onSelect(cmd);
            }}
            onMouseEnter={() => onHover(i)}
            style={{
              padding: "9px 14px",
              cursor: "pointer",
              background: active ? "var(--accent-light)" : "transparent",
              borderLeft: `3px solid ${active ? "var(--accent)" : "transparent"}`,
              display: "flex",
              alignItems: "baseline",
              gap: 12,
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-mono, ui-monospace, monospace)",
                fontSize: 13,
                fontWeight: 600,
                color: active ? "var(--accent)" : "var(--text)",
                minWidth: 96,
              }}
            >
              /{cmd.alias}
            </span>
            <span style={{ flex: 1, minWidth: 0 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
                {cmd.displayName}
              </span>
              <span
                style={{
                  display: "block",
                  fontSize: 11,
                  color: "var(--text-muted)",
                  marginTop: 2,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {cmd.description}
              </span>
            </span>
            {cmd.estimatedSeconds ? (
              <span style={{ fontSize: 10, color: "var(--text-muted)", flexShrink: 0 }}>
                ~{cmd.estimatedSeconds}s
              </span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

const popupStyle: React.CSSProperties = {
  position: "absolute",
  bottom: "calc(100% + 6px)",
  left: 0,
  right: 0,
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md, 10px)",
  boxShadow: "var(--shadow-lg)",
  maxHeight: 340,
  overflowY: "auto",
  zIndex: 50,
};

"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  filterCommands,
  SLASH_COMMANDS,
  SlashCommandPopup,
  type SlashCommand,
} from "@/components/ui/SlashCommandPopup";

// Categories suppressed from the popup. C-class commands moved to the
// Outreach workspace; keyboard nav must use the post-filter list so
// activeIndex never lands on a hidden item.
const HIDDEN_CATEGORIES: SlashCommand["category"][] = ["C"];

// Aliases that trigger the "moved to Outreach" banner. Derived from
// SLASH_COMMANDS so a category change in one place propagates here.
const C_ALIASES = new Set(
  SLASH_COMMANDS.filter((c) => HIDDEN_CATEGORIES.includes(c.category)).map((c) => c.alias),
);

/**
 * The composite input area at the bottom of the chat page:
 *   - attachment chips row
 *   - file picker button
 *   - textarea with auto-resize + slash-command keyboard navigation
 *   - send button
 *
 * Parent owns all state (input text, attachments, streaming flag, slash
 * command list). This component just wires events through.
 */
export function ChatInputBar({
  input,
  onInputChange,
  attachments,
  onRemoveAttachment,
  onPickFile,
  uploading,
  isStreaming,
  slashParsing,
  onSend,
  slashCommands,
  slashActiveIndex,
  onSlashActiveIndexChange,
  onSlashSelect,
  slashServicesError,
  slashServicesLoading,
  onRetrySlashServices,
}: {
  input: string;
  onInputChange: (v: string) => void;
  attachments: string[];
  onRemoveAttachment: (f: string) => void;
  onPickFile: (file: File) => void;
  uploading: boolean;
  isStreaming: boolean;
  slashParsing: boolean;
  onSend: () => void;
  slashCommands: SlashCommand[];
  slashActiveIndex: number;
  onSlashActiveIndexChange: (i: number | ((prev: number) => number)) => void;
  onSlashSelect: (cmd: SlashCommand) => void;
  // Surfaced from useSlashCommand so the popup can show "load failed +
  // retry" instead of silently degrading to slug-only display.
  slashServicesError?: string | null;
  slashServicesLoading?: boolean;
  onRetrySlashServices?: () => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const slashQuery = input.startsWith("/") ? input.slice(1).split(/\s/)[0] : null;
  const slashOpen = slashQuery !== null && !isStreaming;
  const visibleCommands = useMemo(
    () => slashCommands.filter((c) => !HIDDEN_CATEGORIES.includes(c.category)),
    [slashCommands],
  );
  const filtered = slashQuery === null ? [] : filterCommands(visibleCommands, slashQuery);
  const showMigrationBanner = slashQuery !== null && C_ALIASES.has(slashQuery);

  // Auto-resize textarea to fit content (capped at 140px).
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 140) + "px";
    }
  }, [input]);

  // Clamp active slash index when list shrinks.
  useEffect(() => {
    if (slashActiveIndex >= filtered.length && filtered.length > 0) {
      onSlashActiveIndexChange(0);
    }
  }, [filtered.length, slashActiveIndex, onSlashActiveIndexChange]);

  return (
    <div className="chat-input-wrapper">
      <div className="chat-input-container">
        {showMigrationBanner && (
          <div
            data-testid="slash-migration-banner"
            style={{
              padding: "6px 10px",
              margin: "0 0 6px",
              fontSize: 12,
              color: "var(--text-secondary)",
              background: "var(--accent-light)",
              border: "1px solid var(--border-light)",
              borderRadius: "var(--radius-sm, 6px)",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ flex: 1 }}>💡 这个功能已迁到 Outreach 工作台（即将上线），更好用</span>
            <a
              href="#"
              onClick={(e) => e.preventDefault()}
              style={{
                color: "var(--text-muted)",
                textDecoration: "none",
                cursor: "default",
              }}
              aria-disabled="true"
            >
              →
            </a>
          </div>
        )}
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
                <span>
                  {"\uD83D\uDCCE"} {f}
                </span>
                <button onClick={() => onRemoveAttachment(f)} className="attachment-chip-remove">
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
              if (f) onPickFile(f);
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
                commands={filtered}
                activeIndex={slashActiveIndex}
                onSelect={onSlashSelect}
                onHover={onSlashActiveIndexChange}
                hideCategories={HIDDEN_CATEGORIES}
                servicesError={slashServicesError}
                servicesLoading={slashServicesLoading}
                onRetryServices={onRetrySlashServices}
              />
            )}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (slashOpen && filtered.length > 0) {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    onSlashActiveIndexChange((i) => (i + 1) % filtered.length);
                    return;
                  }
                  if (e.key === "ArrowUp") {
                    e.preventDefault();
                    onSlashActiveIndexChange((i) => (i - 1 + filtered.length) % filtered.length);
                    return;
                  }
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    onSlashSelect(filtered[slashActiveIndex]);
                    return;
                  }
                  if (e.key === "Tab") {
                    e.preventDefault();
                    onSlashSelect(filtered[slashActiveIndex]);
                    return;
                  }
                  if (e.key === "Escape") {
                    e.preventDefault();
                    onInputChange("");
                    return;
                  }
                }
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (input.startsWith("/")) return;
                  if (input.trim() && !isStreaming) onSend();
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
            onClick={() => {
              if (slashOpen && filtered.length > 0) {
                onSlashSelect(filtered[slashActiveIndex]);
              } else if (!input.startsWith("/")) {
                onSend();
              }
            }}
            disabled={!input.trim() || isStreaming || slashParsing}
            className="chat-send-btn"
          >
            {isStreaming ? "\u2026" : "\u2191"}
          </button>
        </div>
      </div>
    </div>
  );
}

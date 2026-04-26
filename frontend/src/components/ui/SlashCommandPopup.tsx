"use client";

// Slash-command autocomplete popup for the chat input.
// Shown when the textarea content starts with "/". Filters the 8 report
// services by alias/name. Keyboard nav is driven by the parent (chat page)
// because it owns the textarea.

export interface SlashCommand {
  alias: string; // e.g. "mnc" — what the user types after "/"
  slug: string; // canonical report service slug
  displayName: string; // e.g. "MNC Buyer Profile"
  description: string;
  example: string; // sample query shown in the help bubble + missing-args hint
  estimatedSeconds?: number;
}

// Canonical alias → slug map. Kept in frontend because the short names are
// UX decisions, not part of the backend contract.
// `example` is alias-specific: the help bubble and missing-args hint show it
// verbatim, so it must reflect the kind of input THIS service actually wants
// (a paper query for /paper, an MNC name for /mnc, an asset for /dd, …).
export const SLASH_COMMANDS: Omit<
  SlashCommand,
  "displayName" | "description" | "estimatedSeconds"
>[] = [
  { alias: "paper", slug: "paper-analysis", example: "KRAS G12C 耐药机制 综述 最近3年 15篇" },
  { alias: "mnc", slug: "buyer-profile", example: "AstraZeneca 肿瘤管线" },
  { alias: "dd", slug: "dd-checklist", example: "某 KRAS G12C 抑制剂 III期 BIC 买方视角" },
  { alias: "commercial", slug: "commercial-assessment", example: "三阴乳腺癌 ADC 中国市场" },
  { alias: "disease", slug: "disease-landscape", example: "特发性肺纤维化 全球竞争格局" },
  { alias: "target", slug: "target-radar", example: "IRF5 自免 全球在研" },
  { alias: "ip", slug: "ip-landscape", example: "GLP-1 口服小分子 FTO" },
  { alias: "guidelines", slug: "clinical-guidelines", example: "NSCLC 一线 NCCN 2025" },
  { alias: "evaluate", slug: "deal-evaluator", example: "某 Claudin18.2 ADC 临床II期 买方吸引力" },
  { alias: "rnpv", slug: "rnpv-valuation", example: "某 KRAS G12C 抑制剂 NSCLC 二线 上市概率35%" },
  { alias: "teaser", slug: "deal-teaser", example: "某 BCMA CAR-T 临床I期 寻求海外授权" },
  { alias: "legal", slug: "legal-review", example: "Term Sheet v3 重点看里程碑与终止条款" },
  { alias: "email", slug: "outreach-email", example: "向默沙东 BD 介绍我们的 KRAS G12D 资产" },
  { alias: "company", slug: "company-analysis", example: "Biogen" },
  { alias: "synthesize", slug: "bd-synthesize", example: "Q2 自免 BD 策略 重点 IRF5 / TYK2" },
  { alias: "timing", slug: "timing-advisor", example: "某 Claudin18.2 ADC 何时启动海外 BD" },
  { alias: "log", slug: "outreach-log", example: "2026-04-25 与诺华 BD 通话 讨论 IRF5 资产" },
  { alias: "outreach", slug: "outreach-list", example: "IRF5 自免 找潜在买方 Top 10" },
  {
    alias: "import-reply",
    slug: "import-reply",
    example: "（粘贴对方邮件正文，自动归档为 outreach 记录）",
  },
  { alias: "dataroom", slug: "data-room", example: "某 BCMA CAR-T 临床II期 海外授权 数据室清单" },
  {
    alias: "draft-ts",
    slug: "draft-ts",
    example: "某 KRAS G12D 全球独家许可 首付2000万 里程碑3亿",
  },
  {
    alias: "draft-mta",
    slug: "draft-mta",
    example: "某 anti-PD1 抗体 转让给 Stanford 用于联合用药研究",
  },
  {
    alias: "draft-license",
    slug: "draft-license",
    example: "某 KRAS G12D 全球独家许可 升级为正式 License Agreement",
  },
  {
    alias: "draft-codev",
    slug: "draft-codev",
    example: "某 KRAS G12D 与 BeiGene 共同开发 50/50 全球分成",
  },
  {
    alias: "draft-spa",
    slug: "draft-spa",
    example: "某 biotech 被 MNC 全资收购 EV 5亿美元 cash 80% stock 20%",
  },
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
  // When report-services fetch fails, the popup still renders (commands
  // come from the static SLASH_COMMANDS list) but display_name + description
  // fall back to the bare slug. Surface the failure so users know clicks
  // won't trigger generation until services load.
  servicesError?: string | null;
  servicesLoading?: boolean;
  onRetryServices?: () => void;
}

export function SlashCommandPopup({
  commands,
  activeIndex,
  onSelect,
  onHover,
  servicesError,
  servicesLoading,
  onRetryServices,
}: Props) {
  const errorBanner = servicesError ? (
    <div
      style={{
        padding: "8px 12px",
        background: "#FEF2F2",
        borderBottom: "1px solid var(--border-light)",
        fontSize: 11,
        color: "#B91C1C",
        display: "flex",
        alignItems: "center",
        gap: 8,
      }}
    >
      <span style={{ flex: 1 }}>
        ⚠️ 报告服务列表加载失败 — 命令名/描述不全，点击可能无法触发生成。
      </span>
      {onRetryServices && (
        <button
          type="button"
          onClick={onRetryServices}
          disabled={servicesLoading}
          style={{
            background: "#fff",
            border: "1px solid #FCA5A5",
            borderRadius: 4,
            padding: "2px 8px",
            color: "#B91C1C",
            fontSize: 11,
            fontWeight: 600,
            cursor: servicesLoading ? "wait" : "pointer",
          }}
        >
          {servicesLoading ? "加载中…" : "重试"}
        </button>
      )}
    </div>
  ) : null;

  if (commands.length === 0) {
    return (
      <div style={popupStyle}>
        {errorBanner}
        <div style={{ padding: "12px 14px", fontSize: 13, color: "var(--text-muted)" }}>
          No matching command
        </div>
      </div>
    );
  }

  return (
    <div style={popupStyle} role="listbox">
      {errorBanner}
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

"use client";

import { useState, useRef, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { useSellAsset } from "../layout";
import { generateReport, fetchReportStatus, reportDownloadUrl } from "@/lib/api";

type Audience = "MNC" | "mid-pharma" | "VC";
type Language = "en" | "zh";
type LengthOpt = "one-pager" | "two-pager";
type Emphasis = "efficacy" | "safety" | "IP" | "commercial";
type Stage = "idle" | "running" | "done" | "error";

interface TeaserResult {
  markdown: string;
  files: { filename: string; format: string; download_url: string }[];
}

interface Variant {
  id: number;
  buyer: string;
  taskId: string;
  stage: Stage;
  result: TeaserResult | null;
  error: string | null;
}

const EMPHASIS_OPTS: { v: Emphasis; label: string }[] = [
  { v: "efficacy", label: "疗效 Efficacy" },
  { v: "safety", label: "安全性 Safety" },
  { v: "IP", label: "知识产权 IP" },
  { v: "commercial", label: "商业化 Commercial" },
];

function pollTask(
  taskId: string,
  onDone: (r: TeaserResult) => void,
  onError: (msg: string) => void,
): () => void {
  let alive = true;
  const run = async () => {
    if (!alive) return;
    try {
      const s = await fetchReportStatus(taskId);
      if (!alive) return;
      if (s.status === "completed") {
        onDone({
          markdown: s.result?.markdown ?? "",
          files: (s.result?.files ?? []) as TeaserResult["files"],
        });
      } else if (s.status === "failed") {
        onError(s.error ?? "生成失败");
      } else {
        setTimeout(run, 2000);
      }
    } catch (e) {
      if (alive) onError(e instanceof Error ? e.message : "请求失败");
    }
  };
  setTimeout(run, 1500);
  return () => {
    alive = false;
  };
}

export default function TeaserTabPage() {
  const searchParams = useSearchParams();
  const { asset, loading } = useSellAsset();

  const [audience, setAudience] = useState<Audience>("MNC");
  const [emphasis, setEmphasis] = useState<Emphasis[]>(["efficacy"]);
  const [language, setLanguage] = useState<Language>("zh");
  const [length, setLength] = useState<LengthOpt>("one-pager");

  const [baseStage, setBaseStage] = useState<Stage>("idle");
  const [baseTaskId, setBaseTaskId] = useState<string | null>(null);
  const [baseResult, setBaseResult] = useState<TeaserResult | null>(null);
  const [baseError, setBaseError] = useState<string | null>(null);
  const basePollCleanup = useRef<(() => void) | null>(null);

  const [buyerInput, setBuyerInput] = useState(searchParams?.get("buyer") ?? "");
  const [variants, setVariants] = useState<Variant[]>([]);
  const variantId = useRef(0);

  const buildParams = useCallback(
    (buyerHint?: string) => ({
      audience,
      emphasis,
      language,
      length,
      asset_context: asset?.entity_key ?? "",
      ...(buyerHint ? { buyer_hint: buyerHint } : {}),
    }),
    [audience, emphasis, language, length, asset],
  );

  const handleGenerateBase = useCallback(async () => {
    if (!asset) return;
    basePollCleanup.current?.();
    setBaseStage("running");
    setBaseResult(null);
    setBaseError(null);
    setBaseTaskId(null);
    try {
      const resp = await generateReport("deal-teaser", buildParams());
      setBaseTaskId(resp.task_id);
      if (resp.status === "completed" && resp.result) {
        setBaseResult({
          markdown: resp.result.markdown ?? "",
          files: (resp.result.files ?? []) as TeaserResult["files"],
        });
        setBaseStage("done");
      } else {
        basePollCleanup.current = pollTask(
          resp.task_id,
          (r) => {
            setBaseResult(r);
            setBaseStage("done");
          },
          (err) => {
            setBaseError(err);
            setBaseStage("error");
          },
        );
        setBaseStage("running");
      }
    } catch (e) {
      setBaseError(e instanceof Error ? e.message : "请求失败");
      setBaseStage("error");
    }
  }, [asset, buildParams]);

  const handleGenerateVariant = useCallback(async () => {
    const buyer = buyerInput.trim();
    if (!buyer || !asset) return;
    const id = ++variantId.current;
    setVariants((prev) => [
      { id, buyer, taskId: "", stage: "running", result: null, error: null },
      ...prev,
    ]);
    try {
      const resp = await generateReport("deal-teaser", buildParams(buyer));
      setVariants((prev) => prev.map((v) => (v.id === id ? { ...v, taskId: resp.task_id } : v)));
      if (resp.status === "completed" && resp.result) {
        setVariants((prev) =>
          prev.map((v) =>
            v.id === id
              ? {
                  ...v,
                  stage: "done",
                  result: {
                    markdown: resp.result!.markdown ?? "",
                    files: (resp.result!.files ?? []) as TeaserResult["files"],
                  },
                }
              : v,
          ),
        );
      } else {
        pollTask(
          resp.task_id,
          (r) =>
            setVariants((prev) =>
              prev.map((v) => (v.id === id ? { ...v, stage: "done", result: r } : v)),
            ),
          (err) =>
            setVariants((prev) =>
              prev.map((v) => (v.id === id ? { ...v, stage: "error", error: err } : v)),
            ),
        );
      }
    } catch (e) {
      setVariants((prev) =>
        prev.map((v) =>
          v.id === id
            ? { ...v, stage: "error", error: e instanceof Error ? e.message : "请求失败" }
            : v,
        ),
      );
    }
  }, [buyerInput, asset, buildParams]);

  if (loading && !asset)
    return (
      <Panel>
        <p style={hint}>加载中…</p>
      </Panel>
    );
  if (!asset)
    return (
      <Panel>
        <p style={{ color: "#EF4444", fontSize: 13 }}>无法加载资产。</p>
      </Panel>
    );

  const canVariant = baseStage === "done";

  return (
    <div style={{ display: "flex", gap: 20, alignItems: "flex-start", flexWrap: "wrap" }}>
      {/* Left: form */}
      <div style={{ flex: "0 0 280px", minWidth: 240 }}>
        <Panel>
          <SectionLabel>生成参数</SectionLabel>

          <Field label="受众 Audience">
            <select
              value={audience}
              onChange={(e) => setAudience(e.target.value as Audience)}
              style={sel}
              data-testid="audience-select"
            >
              <option value="MNC">MNC 跨国药企</option>
              <option value="mid-pharma">Mid-pharma 中型药企</option>
              <option value="VC">VC 基金</option>
            </select>
          </Field>

          <Field label="强调点 Emphasis">
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {EMPHASIS_OPTS.map(({ v, label }) => (
                <label key={v} style={chkLabel}>
                  <input
                    type="checkbox"
                    checked={emphasis.includes(v)}
                    onChange={(e) =>
                      setEmphasis((prev) =>
                        e.target.checked ? [...prev, v] : prev.filter((x) => x !== v),
                      )
                    }
                  />
                  {label}
                </label>
              ))}
            </div>
          </Field>

          <Field label="语言 Language">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as Language)}
              style={sel}
              data-testid="language-select"
            >
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
          </Field>

          <Field label="长度 Length">
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {(["one-pager", "two-pager"] as LengthOpt[]).map((v) => (
                <label key={v} style={chkLabel}>
                  <input
                    type="radio"
                    name="teaser-length"
                    value={v}
                    checked={length === v}
                    onChange={() => setLength(v)}
                  />
                  {v === "one-pager" ? "单页 One-pager" : "双页 Two-pager"}
                </label>
              ))}
            </div>
          </Field>

          <button
            onClick={() => void handleGenerateBase()}
            disabled={baseStage === "running"}
            data-testid="generate-base-btn"
            style={{
              ...primaryBtn,
              width: "100%",
              marginTop: 16,
              opacity: baseStage === "running" ? 0.6 : 1,
              cursor: baseStage === "running" ? "not-allowed" : "pointer",
            }}
          >
            {baseStage === "running" ? "生成中…" : "生成基础 Teaser"}
          </button>
        </Panel>
      </div>

      {/* Right: result + buyer customization */}
      <div style={{ flex: 1, minWidth: 300, display: "flex", flexDirection: "column", gap: 16 }}>
        <Panel>
          <SectionLabel>基础 Teaser</SectionLabel>
          {baseStage === "idle" && <p style={hint}>填写左侧参数后点击"生成基础 Teaser"。</p>}
          {baseStage === "running" && <Spinner />}
          {baseStage === "error" && <ErrorBanner msg={baseError ?? "生成失败"} />}
          {baseStage === "done" && baseResult && (
            <>
              <MarkdownPreview md={baseResult.markdown} />
              <DownloadRow taskId={baseTaskId} files={baseResult.files} />
            </>
          )}
        </Panel>

        <Panel>
          <SectionLabel>按 Buyer 定制</SectionLabel>
          <p style={{ ...hint, marginBottom: 10 }}>
            选择已接触的 buyer，基于相同参数生成个性化变体（解决 S2-02）。
          </p>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input
              type="text"
              placeholder="输入 buyer 名称，如 AstraZeneca"
              value={buyerInput}
              onChange={(e) => setBuyerInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleGenerateVariant();
              }}
              style={{ ...inp, flex: 1 }}
              data-testid="buyer-input"
            />
            <button
              onClick={() => void handleGenerateVariant()}
              disabled={!buyerInput.trim() || !canVariant}
              data-testid="generate-variant-btn"
              style={{
                ...primaryBtn,
                flexShrink: 0,
                opacity: !buyerInput.trim() || !canVariant ? 0.5 : 1,
                cursor: !buyerInput.trim() || !canVariant ? "not-allowed" : "pointer",
              }}
            >
              为该 Buyer 定制
            </button>
          </div>
          {variants.length === 0 ? (
            <p style={hint}>尚无定制变体。先生成基础 Teaser，再选 Buyer 定制。</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {variants.map((v) => (
                <VariantCard key={v.id} variant={v} />
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #E8EFFE",
        borderRadius: 12,
        padding: "18px 20px",
        boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
      }}
    >
      {children}
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 11,
        fontWeight: 700,
        color: "#64748B",
        letterSpacing: "0.07em",
        textTransform: "uppercase",
        marginBottom: 14,
      }}
    >
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 6 }}>
        {label}
      </div>
      {children}
    </div>
  );
}

function Spinner() {
  return (
    <div style={{ padding: "24px 0", textAlign: "center", color: "#94A3B8", fontSize: 13 }}>
      ⏳ 生成中，请稍候…
    </div>
  );
}

function ErrorBanner({ msg }: { msg: string }) {
  return (
    <div
      style={{
        padding: "10px 14px",
        background: "#FEF2F2",
        border: "1px solid #FCA5A5",
        borderRadius: 8,
        color: "#991B1B",
        fontSize: 13,
      }}
    >
      {msg}
    </div>
  );
}

function MarkdownPreview({ md }: { md: string }) {
  return (
    <div
      data-testid="markdown-preview"
      style={{
        fontFamily: "var(--font-mono, ui-monospace, monospace)",
        fontSize: 12,
        lineHeight: 1.65,
        color: "#1E293B",
        background: "#F8FAFC",
        border: "1px solid #E2E8F0",
        borderRadius: 8,
        padding: "14px 16px",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
        maxHeight: 480,
        overflowY: "auto",
      }}
    >
      {md || <span style={{ color: "#94A3B8" }}>(空)</span>}
    </div>
  );
}

function DownloadRow({ taskId, files }: { taskId: string | null; files: TeaserResult["files"] }) {
  const docxUrl =
    files.find((f) => f.format === "docx")?.download_url ??
    (taskId ? reportDownloadUrl(taskId, "docx") : null);
  const pptxUrl =
    files.find((f) => f.format === "pptx")?.download_url ??
    (taskId ? reportDownloadUrl(taskId, "pptx") : null);
  if (!docxUrl && !pptxUrl) return null;
  return (
    <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
      {docxUrl && (
        <a href={docxUrl} download style={dlBtn}>
          ⬇ .docx
        </a>
      )}
      {pptxUrl && (
        <a href={pptxUrl} download style={dlBtn}>
          ⬇ .pptx
        </a>
      )}
    </div>
  );
}

function VariantCard({ variant }: { variant: Variant }) {
  const statusColor =
    variant.stage === "done" ? "#166534" : variant.stage === "error" ? "#991B1B" : "#92400E";
  const statusText =
    variant.stage === "running" ? "⏳ 生成中" : variant.stage === "done" ? "✓ 完成" : "✗ 失败";
  return (
    <div
      style={{ border: "1px solid #E2E8F0", borderRadius: 8, overflow: "hidden" }}
      data-testid={`variant-card-${variant.id}`}
    >
      <div
        style={{
          background: "#F8FAFC",
          padding: "8px 14px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: 12,
          fontWeight: 600,
          color: "#374151",
          borderBottom: "1px solid #E2E8F0",
        }}
      >
        <span>🏢 {variant.buyer}</span>
        <span style={{ fontSize: 11, color: statusColor }}>{statusText}</span>
      </div>
      <div style={{ padding: "10px 14px" }}>
        {variant.stage === "running" && <p style={hint}>生成中…</p>}
        {variant.stage === "error" && <ErrorBanner msg={variant.error ?? "失败"} />}
        {variant.stage === "done" && variant.result && (
          <>
            <MarkdownPreview md={variant.result.markdown} />
            <DownloadRow taskId={variant.taskId} files={variant.result.files} />
          </>
        )}
      </div>
    </div>
  );
}

const sel: React.CSSProperties = {
  width: "100%",
  padding: "7px 10px",
  border: "1px solid #D1D5DB",
  borderRadius: 6,
  fontSize: 13,
  color: "#0F172A",
  background: "#fff",
  cursor: "pointer",
};
const inp: React.CSSProperties = {
  padding: "7px 10px",
  border: "1px solid #D1D5DB",
  borderRadius: 6,
  fontSize: 13,
  color: "#0F172A",
  outline: "none",
};
const primaryBtn: React.CSSProperties = {
  padding: "8px 16px",
  background: "#2563EB",
  color: "#fff",
  border: "none",
  borderRadius: 7,
  fontSize: 13,
  fontWeight: 600,
};
const dlBtn: React.CSSProperties = {
  padding: "6px 14px",
  background: "#F1F5F9",
  color: "#0F172A",
  border: "1px solid #E2E8F0",
  borderRadius: 6,
  fontSize: 12,
  fontWeight: 600,
  textDecoration: "none",
  display: "inline-block",
};
const chkLabel: React.CSSProperties = {
  display: "flex",
  gap: 6,
  alignItems: "center",
  fontSize: 13,
  cursor: "pointer",
};
const hint: React.CSSProperties = { fontSize: 13, color: "#94A3B8", margin: 0, lineHeight: 1.5 };

"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchAsset, fetchAssetTrials, updateRecord, deleteRecord } from "@/lib/api";
import { phaseBadgeClass, resultBadgeClass } from "@/lib/badges";
import { parseNum } from "@/lib/format";
import { WatchlistButton } from "@/components/ui/WatchlistButton";
import { EditableField } from "@/components/ui/EditableField";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ReportButton } from "@/components/ui/ReportButton";
import { useAuth } from "@/components/AuthProvider";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface Section {
  title: string;
  fields: [string, string][];
  defaultOpen?: boolean;
}

const SECTIONS: Section[] = [
  {
    title: "Asset Profile",
    defaultOpen: true,
    fields: [
      ["Platform", "技术平台类别"],
      ["Disease", "疾病领域"],
      ["Indication", "适应症"],
      ["Phase", "临床阶段"],
      ["Target", "靶点"],
      ["MOA", "作用机制(MOA)"],
      ["Route", "给药途径"],
      ["Asset Code", "资产代号"],
      ["Regulatory Status", "监管状态"],
      ["Key Trial", "关键试验名称"],
      ["NCT ID", "NCT_ID"],
      ["Enrollment", "入组人数"],
    ],
  },
  {
    title: "BD & Evaluation",
    defaultOpen: true,
    fields: [
      ["POS", "POS预测"],
      ["Peak Sales", "峰值销售预测"],
      ["BD Priority", "BD优先级"],
      ["BD Category", "BD类别"],
      ["Core Asset", "是否核心资产"],
      ["Partner", "合作方"],
      ["Tracking", "追踪状态"],
    ],
  },
  {
    title: "Scoring",
    defaultOpen: true,
    fields: [
      ["Q1 Biology", "Q1_生物学"],
      ["Q2 Drug Form", "Q2_药物形式"],
      ["Q3 Clinical/Regulatory", "Q3_临床监管"],
      ["Q4 Commercial", "Q4_商业交易性"],
      ["Q Total", "Q总分"],
      ["Differentiation Grade", "差异化分级"],
    ],
  },
  {
    title: "Competitive Landscape",
    fields: [
      ["Competition", "竞品情况"],
      ["Differentiation", "差异化描述"],
      ["Risk", "风险因素"],
    ],
  },
  {
    title: "Catalysts",
    fields: [
      ["Next Catalyst", "下一个临床节点"],
      ["Catalyst Date", "节点预计时间"],
      ["Catalyst Calendar", "催化剂日历"],
    ],
  },
  {
    title: "Source & Meta",
    fields: [
      ["BP Source", "BP来源"],
      ["Papers to Check", "待查论文"],
      ["Created", "创建时间"],
      ["Updated", "更新时间"],
      ["Enrich Confidence", "_enrich_confidence"],
      ["Enrich Date", "_enrich_date"],
    ],
  },
];

export default function AssetDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const company = decodeURIComponent(params.company as string);
  const name = decodeURIComponent(params.name as string);

  const [asset, setAsset] = useState<any>(null);
  const [trials, setTrials] = useState<any>(null);
  const [notFound, setNotFound] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const isAdmin = user?.is_admin === true;

  const [openSections, setOpenSections] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    SECTIONS.forEach((s) => {
      init[s.title] = s.defaultOpen ?? false;
    });
    return init;
  });

  useEffect(() => {
    fetchAsset(company, name)
      .then(setAsset)
      .catch(() => setNotFound(true));
    fetchAssetTrials(company, name).then(setTrials);
  }, [company, name]);

  if (notFound) return <div className="loading">Asset not found</div>;
  if (!asset) return <div className="loading">Loading...</div>;

  const handleFieldSave = async (dbCol: string, newValue: string) => {
    await updateRecord("资产", name, { [dbCol]: newValue }, company);
    setAsset({ ...asset, [dbCol]: newValue });
  };

  const handleDelete = async () => {
    await deleteRecord("资产", name, company);
    router.push(`/companies/${encodeURIComponent(company)}`);
  };

  const q1 = parseNum(asset["Q1_生物学"]);
  const q2 = parseNum(asset["Q2_药物形式"]);
  const q3 = parseNum(asset["Q3_临床监管"]);
  const q4 = parseNum(asset["Q4_商业交易性"]);
  const hasScores = q1 != null || q2 != null || q3 != null || q4 != null;

  const radarData = [
    { axis: "Biology (Q1)", value: q1 ?? 0 },
    { axis: "Drug Form (Q2)", value: q2 ?? 0 },
    { axis: "Clinical (Q3)", value: q3 ?? 0 },
    { axis: "Commercial (Q4)", value: q4 ?? 0 },
  ];

  return (
    <div>
      <button
        onClick={() => router.back()}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          margin: "12px 0 0 16px",
          padding: "4px 10px",
          background: "none",
          border: "1px solid #d1d5db",
          borderRadius: 6,
          fontSize: 13,
          color: "#6b7280",
          cursor: "pointer",
        }}
      >
        ← 返回
      </button>
      <div className="detail-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <WatchlistButton entityType="asset" entityKey={name} size={22} />
              <h1 style={{ margin: 0 }}>{name}</h1>
              <ReportButton entityType="资产" entityKey={name} />
            </div>
            <div className="meta">
              <span
                style={{ cursor: "pointer", textDecoration: "underline" }}
                onClick={() => router.push(`/companies/${encodeURIComponent(company)}`)}
              >
                {company}
              </span>
              {asset["临床阶段"] && (
                <span className={`badge ${phaseBadgeClass(asset["临床阶段"])}`}>
                  {asset["临床阶段"]}
                </span>
              )}
              {asset["疾病领域"] && <span>{asset["疾病领域"]}</span>}
              {asset["靶点"] && <span>Target: {asset["靶点"]}</span>}
            </div>
          </div>
          {isAdmin && (
            <button
              onClick={() => setShowDelete(true)}
              style={{
                padding: "0.4rem 0.9rem",
                background: "white",
                color: "var(--red)",
                border: "1px solid var(--red)",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: "0.8rem",
              }}
            >
              Delete
            </button>
          )}
        </div>
      </div>

      {hasScores && (
        <div className="card" style={{ marginBottom: "0.75rem" }}>
          <h3 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>Evaluation Scores</h3>
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="axis" fontSize={11} />
              <PolarRadiusAxis domain={[0, 5]} tickCount={6} fontSize={10} />
              <Radar dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.25} />
              <Tooltip />
            </RadarChart>
          </ResponsiveContainer>
          <div style={{ textAlign: "center", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
            Q1: {q1 ?? "-"} | Q2: {q2 ?? "-"} | Q3: {q3 ?? "-"} | Q4: {q4 ?? "-"}
            {asset["Q总分"] && ` | Total: ${asset["Q总分"]}`}
          </div>
        </div>
      )}

      {asset["资产描述"] && (
        <div className="card" style={{ marginBottom: "0.75rem" }}>
          <h3 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>Description</h3>
          <p
            style={{
              margin: 0,
              fontSize: "0.85rem",
              color: "var(--text-secondary)",
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
            }}
          >
            {asset["资产描述"]}
          </p>
        </div>
      )}

      {SECTIONS.map((section) => (
        <div key={section.title} className="card" style={{ marginBottom: "0.75rem" }}>
          <h3
            onClick={() =>
              setOpenSections((prev) => ({ ...prev, [section.title]: !prev[section.title] }))
            }
            style={{
              margin: 0,
              fontSize: "0.95rem",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
            }}
          >
            <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>
              {openSections[section.title] ? "\u25BC" : "\u25B6"}
            </span>
            {section.title}
          </h3>
          {openSections[section.title] && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
                gap: "0.6rem",
                fontSize: "0.85rem",
                marginTop: "0.75rem",
              }}
            >
              {section.fields.map(([label, dbCol]) =>
                isAdmin ? (
                  <EditableField
                    key={dbCol}
                    label={label}
                    value={String(asset[dbCol] ?? "")}
                    onSave={(v) => handleFieldSave(dbCol, v)}
                  />
                ) : (
                  <div key={dbCol} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <span
                      style={{
                        fontSize: "0.7rem",
                        color: "var(--text-secondary)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        fontWeight: 600,
                      }}
                    >
                      {label}
                    </span>
                    <span
                      style={{
                        fontSize: "0.85rem",
                        color: asset[dbCol] ? "var(--text)" : "var(--text-secondary)",
                      }}
                    >
                      {asset[dbCol] || "—"}
                    </span>
                  </div>
                ),
              )}
            </div>
          )}
        </div>
      ))}

      <div className="card">
        <h3 style={{ margin: "0 0 1rem", fontSize: "0.95rem" }}>
          Clinical Trials ({trials?.total ?? "..."})
        </h3>
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Trial ID</th>
                <th>Indication</th>
                <th>Phase</th>
                <th>Arm</th>
                <th>Primary Endpoint</th>
                <th>Value</th>
                <th>Result</th>
                <th>Safety</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {trials?.data?.map((t: any) => (
                <tr key={t["记录ID"]}>
                  <td>{t["试验ID"]}</td>
                  <td>{t["适应症"]?.slice(0, 35) || "-"}</td>
                  <td>
                    <span className={`badge ${phaseBadgeClass(t["临床期次"])}`}>
                      {t["临床期次"] || "-"}
                    </span>
                  </td>
                  <td>{t["臂名称"] || "-"}</td>
                  <td>{t["主要终点名称"] || "-"}</td>
                  <td>
                    {t["主要终点结果值"] != null
                      ? `${t["主要终点结果值"]}${t["主要终点单位"] || ""}`
                      : "-"}
                  </td>
                  <td>
                    <span className={`badge ${resultBadgeClass(t["结果判定"])}`}>
                      {t["结果判定"] || "-"}
                    </span>
                  </td>
                  <td>{t["安全性标志"] || "-"}</td>
                  <td>{t["数据状态"] || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {showDelete && isAdmin && (
        <ConfirmDialog
          message={`Delete asset "${name}" (${company})?`}
          onConfirm={handleDelete}
          onCancel={() => setShowDelete(false)}
        />
      )}
    </div>
  );
}

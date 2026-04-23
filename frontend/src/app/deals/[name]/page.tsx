"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchDeal, updateRecord, deleteRecord } from "@/lib/api";
import { phaseBadgeClass } from "@/lib/badges";
import { EditableField } from "@/components/ui/EditableField";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ReportButton } from "@/components/ui/ReportButton";
import { useAuth } from "@/components/AuthProvider";

interface Section {
  title: string;
  fields: [string, string][];
}

const SECTIONS: Section[] = [
  {
    title: "Deal Overview",
    fields: [
      ["Deal Type", "交易类型"],
      ["Buyer", "买方公司"],
      ["Buyer CRM Status", "买方跟进状态"],
      ["Seller / Partner", "卖方/合作方"],
      ["Seller CRM Status", "卖方跟进状态"],
      ["Asset", "资产名称"],
      ["Target", "靶点"],
      ["Phase", "临床阶段"],
      ["Indication", "适应症"],
      ["Platform", "技术平台"],
    ],
  },
  {
    title: "Financials",
    fields: [
      ["Upfront ($M)", "首付款($M)"],
      ["Milestone Total ($M)", "里程碑总额($M)"],
      ["Deal Total ($M)", "交易总额($M)"],
      ["Royalty Structure", "特许权结构"],
      ["Milestones", "里程碑节点"],
    ],
  },
  {
    title: "Analysis",
    fields: [
      ["News Title", "新闻标题"],
      ["Source Link", "来源链接"],
      ["Strategic Score", "战略评分"],
      ["Strategic Analysis", "战略解读"],
    ],
  },
  {
    title: "Meta",
    fields: [
      ["Announced Date", "宣布日期"],
      ["Discovery Source", "发现来源"],
      ["Discovery Time", "发现时间"],
      ["Auto-created Company", "是否自动创建公司"],
      ["Notes", "备注"],
    ],
  },
];

export default function DealDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const name = decodeURIComponent(params.name as string);
  const isAdmin = user?.is_admin === true;

  const [deal, setDeal] = useState<any>(null);
  const [notFound, setNotFound] = useState(false);
  const [showDelete, setShowDelete] = useState(false);

  useEffect(() => {
    fetchDeal(name)
      .then(setDeal)
      .catch(() => setNotFound(true));
  }, [name]);

  if (notFound) return <div className="loading">Deal not found</div>;
  if (!deal) return <div className="loading">Loading...</div>;

  const handleFieldSave = async (dbCol: string, newValue: string) => {
    await updateRecord("交易", name, { [dbCol]: newValue });
    setDeal({ ...deal, [dbCol]: newValue });
  };

  const handleDelete = async () => {
    await deleteRecord("交易", name);
    router.push("/deals");
  };

  return (
    <div>
      <div className="detail-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <h1 style={{ fontSize: "1.3rem", margin: 0 }}>{name}</h1>
              <ReportButton entityType="交易" entityKey={name} />
            </div>
            <div className="meta">
              {deal["交易类型"] && <span className="badge badge-blue">{deal["交易类型"]}</span>}
              {deal["买方公司"] && (
                <span
                  style={{ cursor: "pointer", textDecoration: "underline" }}
                  onClick={() => router.push(`/companies/${encodeURIComponent(deal["买方公司"])}`)}
                >
                  Buyer: {deal["买方公司"]}
                </span>
              )}
              {deal["卖方/合作方"] && (
                <span
                  style={{ cursor: "pointer", textDecoration: "underline" }}
                  onClick={() =>
                    router.push(`/companies/${encodeURIComponent(deal["卖方/合作方"])}`)
                  }
                >
                  Seller: {deal["卖方/合作方"]}
                </span>
              )}
              {deal["宣布日期"] && <span>{deal["宣布日期"]}</span>}
              {deal["临床阶段"] && (
                <span className={`badge ${phaseBadgeClass(deal["临床阶段"])}`}>
                  {deal["临床阶段"]}
                </span>
              )}
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

      {/* Financial summary card */}
      {(deal["首付款($M)"] || deal["交易总额($M)"]) && (
        <div
          className="card"
          style={{ marginBottom: "1rem", display: "flex", gap: "2rem", fontSize: "0.9rem" }}
        >
          {deal["首付款($M)"] && (
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>Upfront</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>${deal["首付款($M)"]}M</div>
            </div>
          )}
          {deal["里程碑总额($M)"] && (
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>Milestones</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>${deal["里程碑总额($M)"]}M</div>
            </div>
          )}
          {deal["交易总额($M)"] && (
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                Total Deal Value
              </div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--accent)" }}>
                ${deal["交易总额($M)"]}M
              </div>
            </div>
          )}
          {deal["战略评分"] && (
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                Strategic Score
              </div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{deal["战略评分"]}</div>
            </div>
          )}
        </div>
      )}

      {/* Strategic analysis card */}
      {deal["战略解读"] && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h3 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>Strategic Analysis</h3>
          <p
            style={{
              margin: 0,
              fontSize: "0.85rem",
              color: "var(--text-secondary)",
              lineHeight: 1.6,
            }}
          >
            {deal["战略解读"]}
          </p>
        </div>
      )}

      {SECTIONS.map((section) => (
        <div key={section.title} className="card" style={{ marginBottom: "0.75rem" }}>
          <h3 style={{ margin: "0 0 0.75rem", fontSize: "0.95rem" }}>{section.title}</h3>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
              gap: "0.6rem",
              fontSize: "0.85rem",
            }}
          >
            {section.fields.map(([label, dbCol]) =>
              isAdmin ? (
                <EditableField
                  key={dbCol}
                  label={label}
                  value={String(deal[dbCol] ?? "")}
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
                      color: deal[dbCol] ? "var(--text)" : "var(--text-secondary)",
                    }}
                  >
                    {deal[dbCol] || "\u2014"}
                  </span>
                </div>
              ),
            )}
          </div>
        </div>
      ))}

      {showDelete && isAdmin && (
        <ConfirmDialog
          message={`Delete deal "${name}"?`}
          onConfirm={handleDelete}
          onCancel={() => setShowDelete(false)}
        />
      )}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchCompany, fetchCompanyAssets, fetchCompanyTrials, fetchCompanyDeals, fetchBuyer, updateRecord, deleteRecord, renameCompany } from "@/lib/api";
import { phaseBadgeClass, priorityBadgeClass, resultBadgeClass } from "@/lib/utils";
import { EditableField } from "@/components/ui/EditableField";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { BPUpload } from "@/components/ui/BPUpload";
import { AgentButton } from "@/components/ui/AgentButton";

interface Section { title: string; fields: [string, string][]; defaultOpen?: boolean; }

const SECTIONS: Section[] = [
  {
    title: "Company Profile",
    defaultOpen: true,
    fields: [
      ["Type", "客户类型"],
      ["Country", "所处国家"],
      ["Ticker", "Ticker"],
      ["English Name", "英文名"],
      ["Chinese Name", "中文名"],
      ["Former Name", "曾用名"],
      ["Parent Company", "母公司"],
      ["Website", "网址"],
      ["Valuation", "市值/估值"],
      ["Revenue", "年收入"],
      ["Cash", "现金"],
    ],
  },
  {
    title: "Pipeline & Science",
    defaultOpen: true,
    fields: [
      ["Core Pipeline", "主要核心pipeline的名字"],
      ["Platform Type", "主要资产或技术平台的类型"],
      ["Disease Area", "疾病领域"],
      ["Stage", "核心产品的阶段"],
      ["Indication", "核心资产主要适应症"],
      ["POS", "POS预测"],
      ["Quality Score", "公司质量评分"],
    ],
  },
  {
    title: "BD & Tracking",
    defaultOpen: true,
    fields: [
      ["BD Priority", "BD跟进优先级"],
      ["Deal Type", "推荐交易类型"],
      ["BD Status", "BD状态"],
      ["BD Source", "BD来源"],
      ["Tracking", "追踪状态"],
      ["Follow-up Advice", "跟进建议"],
      ["Potential Buyers", "潜在买方"],
      ["Contact", "联系人"],
    ],
  },
  {
    title: "Catalysts & Timeline",
    fields: [
      ["Next Catalyst", "下一个临床节点"],
      ["Catalyst Date", "节点预计时间"],
      ["Catalyst Calendar", "催化剂日历"],
      ["Analysis Date", "分析的日期"],
      ["Last Modified", "更改日期"],
    ],
  },
  {
    title: "Attachments & Notes",
    fields: [
      ["BP Source", "BP来源"],
      ["Notes", "备注"],
    ],
  },
];

export default function CompanyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const name = decodeURIComponent(params.name as string);

  const [company, setCompany] = useState<any>(null);
  const [assets, setAssets] = useState<any>(null);
  const [trials, setTrials] = useState<any>(null);
  const [deals, setDeals] = useState<any[]>([]);
  const [buyerProfile, setBuyerProfile] = useState<any>(null);
  const [tab, setTab] = useState("assets");
  const [notFound, setNotFound] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [openSections, setOpenSections] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    SECTIONS.forEach((s) => { init[s.title] = s.defaultOpen ?? false; });
    return init;
  });

  const reload = () => {
    fetchCompany(name).then(setCompany).catch(() => setNotFound(true));
    fetchCompanyAssets(name).then(setAssets);
    fetchCompanyTrials(name).then(setTrials);
    fetchCompanyDeals(name).then(setDeals);
    fetchBuyer(name).then(setBuyerProfile).catch(() => {});
  };

  useEffect(() => { reload(); }, [name]);

  if (notFound) return <div className="loading">Company not found</div>;
  if (!company) return <div className="loading">Loading...</div>;

  const handleFieldSave = async (dbColumn: string, newValue: string) => {
    await updateRecord("公司", name, { [dbColumn]: newValue });
    setCompany({ ...company, [dbColumn]: newValue });
  };

  const handleDelete = async () => {
    await deleteRecord("公司", name);
    router.push("/companies");
  };

  return (
    <div>
      <div className="detail-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            {editingName ? (
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  autoFocus
                  value={draftName}
                  onChange={(e) => setDraftName(e.target.value)}
                  onKeyDown={async (e) => {
                    if (e.key === "Escape") { setEditingName(false); return; }
                    if (e.key === "Enter" && draftName.trim() && draftName !== name) {
                      try {
                        await renameCompany(name, draftName.trim());
                        router.replace(`/companies/${encodeURIComponent(draftName.trim())}`);
                      } catch (err: any) { alert(err.message); }
                    }
                  }}
                  onBlur={() => setEditingName(false)}
                  style={{ fontSize: "1.5rem", fontWeight: 700, border: "1px solid var(--accent)", borderRadius: 6, padding: "0.1rem 0.4rem", width: "100%" }}
                />
              </div>
            ) : (
              <h1
                onClick={() => { setDraftName(name); setEditingName(true); }}
                style={{ cursor: "pointer" }}
                title="Click to rename"
              >
                {name} <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)", opacity: 0.5 }}>&#9998;</span>
              </h1>
            )}
            <div className="meta">
              {company["客户类型"] && <span>{company["客户类型"]}</span>}
              {company["所处国家"] && <span>{company["所处国家"]}</span>}
              {company["Ticker"] && <span>{company["Ticker"]}</span>}
              {company["BD跟进优先级"] && (
                <span className={`badge ${priorityBadgeClass(company["BD跟进优先级"])}`}>
                  Priority {company["BD跟进优先级"]}
                </span>
              )}
            </div>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "flex-start" }}>
            <AgentButton
              label="Enrich Data"
              message={`@分析 ${name}`}
              onComplete={reload}
            />
            <button
              onClick={() => setShowUpload(true)}
              style={{
                padding: "0.4rem 0.9rem", background: "#8b5cf6", color: "white",
                border: "none", borderRadius: 6, cursor: "pointer", fontSize: "0.8rem", fontWeight: 600,
              }}
            >
              Upload BP
            </button>
            <button
              onClick={() => setShowDelete(true)}
              style={{
                padding: "0.4rem 0.9rem", background: "white", color: "var(--red)",
                border: "1px solid var(--red)", borderRadius: 6, cursor: "pointer", fontSize: "0.8rem",
              }}
            >
              Delete
            </button>
          </div>
        </div>
      </div>

      {/* BP Attachment */}
      {company["BP来源"] && (
        <div style={{ marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.85rem" }}>
          <span style={{ color: "var(--text-secondary)" }}>BP Attached:</span>
          <a
            href={`/api/files/bp/${encodeURIComponent(company["BP来源"])}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "var(--accent)", fontWeight: 600, textDecoration: "underline" }}
          >
            {company["BP来源"]}
          </a>
        </div>
      )}

      {SECTIONS.map((section) => (
        <div key={section.title} className="card" style={{ marginBottom: "0.75rem" }}>
          <h3
            onClick={() => setOpenSections((prev) => ({ ...prev, [section.title]: !prev[section.title] }))}
            style={{ margin: 0, fontSize: "0.95rem", cursor: "pointer", display: "flex", alignItems: "center", gap: "0.5rem" }}
          >
            <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>
              {openSections[section.title] ? "\u25BC" : "\u25B6"}
            </span>
            {section.title}
          </h3>
          {openSections[section.title] && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "0.6rem", fontSize: "0.85rem", marginTop: "0.75rem" }}>
              {section.fields.map(([label, dbCol]) => (
                <EditableField
                  key={dbCol}
                  label={label}
                  value={company[dbCol] || ""}
                  onSave={(v) => handleFieldSave(dbCol, v)}
                />
              ))}
            </div>
          )}
        </div>
      ))}

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab ${tab === "assets" ? "active" : ""}`} onClick={() => setTab("assets")}>
          Assets ({assets?.total ?? "..."})
        </button>
        <button className={`tab ${tab === "trials" ? "active" : ""}`} onClick={() => setTab("trials")}>
          Clinical ({trials?.total ?? "..."})
        </button>
        <button className={`tab ${tab === "deals" ? "active" : ""}`} onClick={() => setTab("deals")}>
          Deals ({deals?.length ?? "..."})
        </button>
        {buyerProfile && (
          <button className={`tab ${tab === "buyer" ? "active" : ""}`} onClick={() => setTab("buyer")}>
            Buyer Profile
          </button>
        )}
      </div>

      {tab === "assets" && (
        <div className="card">
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Asset</th><th>Platform</th><th>Disease</th><th>Indication</th><th>Phase</th><th>Target</th><th>Score</th>
                </tr>
              </thead>
              <tbody>
                {assets?.data?.map((a: any) => (
                  <tr key={`${a["资产名称"]}-${a["所属客户"]}`} onClick={() => router.push(`/assets/${encodeURIComponent(a["所属客户"])}/${encodeURIComponent(a["资产名称"])}`)}>
                    <td style={{ fontWeight: 600 }}>{a["资产名称"]}</td>
                    <td>{a["技术平台类别"] || "-"}</td>
                    <td>{a["疾病领域"] || "-"}</td>
                    <td>{a["适应症"] || "-"}</td>
                    <td><span className={`badge ${phaseBadgeClass(a["临床阶段"])}`}>{a["临床阶段"] || "-"}</span></td>
                    <td>{a["靶点"] || "-"}</td>
                    <td>{a["质量评分"] || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "trials" && (
        <div className="card">
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Trial ID</th><th>Asset</th><th>Indication</th><th>Phase</th><th>Primary Endpoint</th><th>Result</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {trials?.data?.map((t: any) => (
                  <tr key={t["记录ID"]}>
                    <td>{t["试验ID"]}</td>
                    <td>{t["资产名称"]}</td>
                    <td>{t["适应症"]?.slice(0, 40) || "-"}</td>
                    <td><span className={`badge ${phaseBadgeClass(t["临床期次"])}`}>{t["临床期次"] || "-"}</span></td>
                    <td>{t["主要终点名称"] || "-"}</td>
                    <td><span className={`badge ${resultBadgeClass(t["结果判定"])}`}>{t["结果判定"] || "-"}</span></td>
                    <td>{t["数据状态"] || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "deals" && (
        <div className="card">
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Deal</th><th>Type</th><th>Buyer</th><th>Seller</th><th>Asset</th><th>Upfront ($M)</th><th>Total ($M)</th><th>Date</th>
                </tr>
              </thead>
              <tbody>
                {deals?.map((d: any) => (
                  <tr key={d["交易名称"]} onClick={() => router.push(`/deals?q=${encodeURIComponent(d["交易名称"])}`)}>
                    <td style={{ fontWeight: 600 }}>{d["交易名称"]}</td>
                    <td>{d["交易类型"] || "-"}</td>
                    <td>{d["买方公司"] || "-"}</td>
                    <td>{d["卖方/合作方"] || "-"}</td>
                    <td>{d["资产名称"] || "-"}</td>
                    <td>{d["首付款($M)"] || "-"}</td>
                    <td>{d["交易总额($M)"] || "-"}</td>
                    <td>{d["宣布日期"] || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "buyer" && buyerProfile && (
        <div className="card">
          {buyerProfile.dna_summary && (
            <div style={{ marginBottom: "1rem" }}>
              <h3 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>DNA Summary</h3>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {buyerProfile.dna_summary}
              </p>
            </div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "0.5rem", fontSize: "0.85rem", marginBottom: "1rem" }}>
            {[
              ["Heritage TA", buyerProfile.heritage_ta],
              ["Risk Appetite", buyerProfile.risk_appetite],
              ["Deal Size", buyerProfile.deal_size_preference],
              ["CEO", buyerProfile.ceo_name],
              ["Head of BD", buyerProfile.head_bd_name],
            ].map(([label, value]) => (
              <div key={label}>
                <span style={{ color: "var(--text-secondary)" }}>{label}: </span>
                <strong>{value || "-"}</strong>
              </div>
            ))}
          </div>
          <button
            onClick={() => router.push(`/buyers/${encodeURIComponent(name)}`)}
            style={{ padding: "0.4rem 0.9rem", background: "var(--accent)", color: "white", border: "none", borderRadius: 6, cursor: "pointer", fontSize: "0.85rem", fontWeight: 600 }}
          >
            View Full Profile &rarr;
          </button>
        </div>
      )}

      {showDelete && (
        <ConfirmDialog
          message={`Delete company "${name}" and all associated data?`}
          onConfirm={handleDelete}
          onCancel={() => setShowDelete(false)}
        />
      )}

      {showUpload && (
        <BPUpload
          company={name}
          onClose={() => setShowUpload(false)}
          onUploaded={(filename) => {
            setCompany({ ...company, "BP来源": filename });
          }}
        />
      )}
    </div>
  );
}

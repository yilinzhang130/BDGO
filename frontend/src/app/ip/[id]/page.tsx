"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchPatent, updateRecord, deleteRecord } from "@/lib/api";
import { statusBadgeClass } from "@/lib/utils";
import { EditableField } from "@/components/ui/EditableField";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";

const INFO_FIELDS: [string, string][] = [
  ["Patent Number", "专利号"],
  ["Holder", "专利持有人"],
  ["Related Asset", "关联资产"],
  ["Related Company", "关联公司"],
  ["Patent Type", "专利类型"],
  ["Filing Date", "申请日"],
  ["Grant Date", "授权日"],
  ["Expiry Date", "到期日"],
  ["PTE Extended Expiry", "PTE延期到期日"],
  ["Claims Summary", "权利要求摘要"],
  ["Patent Family", "专利族"],
  ["Status", "状态"],
  ["Jurisdiction", "管辖区"],
  ["Orange Book", "Orange_Book"],
  ["Source", "来源"],
  ["Notes", "备注"],
  ["Tracking", "追踪状态"],
];

export default function PatentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = decodeURIComponent(params.id as string);

  const [patent, setPatent] = useState<any>(null);
  const [notFound, setNotFound] = useState(false);
  const [showDelete, setShowDelete] = useState(false);

  useEffect(() => {
    fetchPatent(id).then(setPatent).catch(() => setNotFound(true));
  }, [id]);

  if (notFound) return <div className="loading">Patent not found</div>;
  if (!patent) return <div className="loading">Loading...</div>;

  const handleFieldSave = async (dbCol: string, newValue: string) => {
    await updateRecord("IP", id, { [dbCol]: newValue });
    setPatent({ ...patent, [dbCol]: newValue });
  };

  const handleDelete = async () => {
    await deleteRecord("IP", id);
    router.push("/ip");
  };

  return (
    <div>
      <div className="detail-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1>{patent["专利号"]}</h1>
            <div className="meta">
              {patent["关联公司"] && (
                <span
                  style={{ cursor: "pointer", textDecoration: "underline" }}
                  onClick={() => router.push(`/companies/${encodeURIComponent(patent["关联公司"])}`)}
                >
                  {patent["关联公司"]}
                </span>
              )}
              {patent["状态"] && (
                <span className={`badge ${statusBadgeClass(patent["状态"])}`}>{patent["状态"]}</span>
              )}
              {patent["管辖区"] && <span>{patent["管辖区"]}</span>}
              {patent["专利类型"] && <span>{patent["专利类型"]}</span>}
            </div>
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              onClick={() => setShowDelete(true)}
              style={{ padding: "0.4rem 0.9rem", background: "white", color: "var(--red)", border: "1px solid var(--red)", borderRadius: 6, cursor: "pointer", fontSize: "0.8rem" }}
            >
              Delete
            </button>
          </div>
        </div>
      </div>

      {/* Date summary card */}
      {(patent["申请日"] || patent["到期日"]) && (
        <div className="card" style={{ marginBottom: "1rem", display: "flex", gap: "2rem", fontSize: "0.9rem" }}>
          {patent["申请日"] && (
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>Filing Date</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 600 }}>{patent["申请日"]}</div>
            </div>
          )}
          {patent["授权日"] && (
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>Grant Date</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 600 }}>{patent["授权日"]}</div>
            </div>
          )}
          {patent["到期日"] && (
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>Expiry Date</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 600, color: "var(--red)" }}>{patent["到期日"]}</div>
            </div>
          )}
          {patent["PTE延期到期日"] && (
            <div>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>PTE Extended Expiry</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 600 }}>{patent["PTE延期到期日"]}</div>
            </div>
          )}
        </div>
      )}

      {/* Claims summary */}
      {patent["权利要求摘要"] && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h3 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>Claims Summary</h3>
          <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
            {patent["权利要求摘要"]}
          </p>
        </div>
      )}

      <div className="card">
        <h3 style={{ margin: "0 0 1rem", fontSize: "0.95rem" }}>Patent Details</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: "0.6rem", fontSize: "0.85rem" }}>
          {INFO_FIELDS.map(([label, dbCol]) => (
            <EditableField
              key={dbCol}
              label={label}
              value={String(patent[dbCol] ?? "")}
              onSave={(v) => handleFieldSave(dbCol, v)}
            />
          ))}
        </div>
      </div>

      {showDelete && (
        <ConfirmDialog
          message={`Delete patent "${patent["专利号"]}"?`}
          onConfirm={handleDelete}
          onCancel={() => setShowDelete(false)}
        />
      )}
    </div>
  );
}

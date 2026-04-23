"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchBuyer, updateRecord } from "@/lib/api";
import { safeJsonParse } from "@/lib/format";
import { EditableField } from "@/components/ui/EditableField";

const SCALAR_FIELDS: [string, string][] = [
  ["Company", "company_name"],
  ["Chinese Name", "company_cn"],
  ["Founded Year", "founded_year"],
  ["Heritage TA", "heritage_ta"],
  ["Innovation Philosophy", "innovation_philosophy"],
  ["Risk Appetite", "risk_appetite"],
  ["Deal Size Preference", "deal_size_preference"],
  ["Integration Success Rate", "integration_success_rate"],
  ["Annual Revenue", "annual_revenue"],
  ["Revenue Year", "annual_revenue_year"],
  ["CEO", "ceo_name"],
  ["CEO Background", "ceo_background"],
  ["CSO", "cso_name"],
  ["CSO Background", "cso_background"],
  ["Head of BD", "head_bd_name"],
  ["Head of BD Background", "head_bd_background"],
  ["Last Updated", "last_updated"],
];

function CapabilityMap({ data }: { data: Record<string, string> }) {
  if (!data || typeof data !== "object")
    return <span style={{ color: "var(--text-secondary)" }}>-</span>;
  const colorMap: Record<string, string> = {
    strong: "#10b981",
    moderate: "#f59e0b",
    minimal: "#94a3b8",
    growing: "#3b82f6",
  };
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
      {Object.entries(data).map(([ta, level]) => (
        <span
          key={ta}
          style={{
            padding: "0.2rem 0.6rem",
            borderRadius: 9999,
            fontSize: "0.75rem",
            fontWeight: 500,
            background: `${colorMap[level] || "#94a3b8"}20`,
            color: colorMap[level] || "#94a3b8",
            border: `1px solid ${colorMap[level] || "#94a3b8"}40`,
          }}
        >
          {ta}: {level}
        </span>
      ))}
    </div>
  );
}

function BDTheses({ data }: { data: any[] }) {
  if (!Array.isArray(data) || data.length === 0)
    return <span style={{ color: "var(--text-secondary)" }}>-</span>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
      {data.map((thesis, i) => (
        <div
          key={i}
          style={{
            padding: "0.6rem",
            background: "var(--bg)",
            borderRadius: 8,
            fontSize: "0.85rem",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>{thesis.thesis}</div>
          <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem" }}>
            {thesis.deal_count} deals | ${thesis.total_invested_m?.toLocaleString()}M invested
          </div>
          {thesis.deals && (
            <div
              style={{ marginTop: "0.25rem", fontSize: "0.75rem", color: "var(--text-secondary)" }}
            >
              {thesis.deals.join(" | ")}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function SunkCostMap({ data }: { data: Record<string, any> }) {
  if (!data || typeof data !== "object")
    return <span style={{ color: "var(--text-secondary)" }}>-</span>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
      {Object.entries(data).map(([ta, info]) => (
        <div
          key={ta}
          style={{
            display: "flex",
            justifyContent: "space-between",
            padding: "0.4rem 0.6rem",
            background: "var(--bg)",
            borderRadius: 6,
            fontSize: "0.85rem",
          }}
        >
          <span style={{ fontWeight: 600 }}>{ta}</span>
          <span style={{ color: "var(--text-secondary)" }}>
            ${info.invested_m?.toLocaleString()}M ({info.deal_count} deals)
          </span>
        </div>
      ))}
    </div>
  );
}

function DealTypePref({ data }: { data: Record<string, number> }) {
  if (!data || typeof data !== "object")
    return <span style={{ color: "var(--text-secondary)" }}>-</span>;
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
      {Object.entries(data)
        .sort((a, b) => b[1] - a[1])
        .map(([type, count]) => (
          <span
            key={type}
            style={{
              padding: "0.2rem 0.6rem",
              background: "var(--bg)",
              borderRadius: 6,
              fontSize: "0.8rem",
            }}
          >
            {type}: {count} ({total > 0 ? Math.round((count / total) * 100) : 0}%)
          </span>
        ))}
    </div>
  );
}

export default function BuyerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const name = decodeURIComponent(params.name as string);

  const [buyer, setBuyer] = useState<any>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    fetchBuyer(name)
      .then(setBuyer)
      .catch(() => setNotFound(true));
  }, [name]);

  const capabilities = useMemo(
    () => (buyer ? safeJsonParse(buyer.commercial_capabilities) : null),
    [buyer],
  );
  const theses = useMemo(() => (buyer ? safeJsonParse(buyer.bd_pattern_theses) : null), [buyer]);
  const sunkCost = useMemo(() => (buyer ? safeJsonParse(buyer.sunk_cost_by_ta) : null), [buyer]);
  const dealTypePref = useMemo(
    () => (buyer ? safeJsonParse(buyer.deal_type_preference) : null),
    [buyer],
  );

  if (notFound) return <div className="loading">Buyer profile not found</div>;
  if (!buyer) return <div className="loading">Loading...</div>;

  const handleFieldSave = async (dbCol: string, newValue: string) => {
    await updateRecord("MNC画像", name, { [dbCol]: newValue });
    setBuyer({ ...buyer, [dbCol]: newValue });
  };

  return (
    <div>
      <div className="detail-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1>{name}</h1>
            <div className="meta">
              {buyer.company_cn && <span>{buyer.company_cn}</span>}
              {buyer.heritage_ta && <span className="badge badge-blue">{buyer.heritage_ta}</span>}
              {buyer.deal_size_preference && <span>{buyer.deal_size_preference}</span>}
              {buyer.last_updated && <span>Updated: {buyer.last_updated}</span>}
            </div>
          </div>
          <button
            onClick={() => router.push(`/companies/${encodeURIComponent(name)}`)}
            style={{
              padding: "0.4rem 0.9rem",
              background: "var(--accent)",
              color: "white",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
              fontSize: "0.8rem",
              fontWeight: 600,
            }}
          >
            View Company
          </button>
        </div>
      </div>

      {/* DNA Summary */}
      {buyer.dna_summary && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h3 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>DNA Summary</h3>
          <p
            style={{
              margin: 0,
              fontSize: "0.85rem",
              color: "var(--text-secondary)",
              lineHeight: 1.7,
              whiteSpace: "pre-wrap",
            }}
          >
            {buyer.dna_summary}
          </p>
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "1rem",
          marginBottom: "1rem",
        }}
      >
        {/* Commercial Capabilities */}
        <div className="card">
          <h3 style={{ margin: "0 0 0.75rem", fontSize: "0.95rem" }}>Commercial Capabilities</h3>
          <CapabilityMap data={capabilities} />
        </div>

        {/* Deal Type Preferences */}
        <div className="card">
          <h3 style={{ margin: "0 0 0.75rem", fontSize: "0.95rem" }}>Deal Type Preferences</h3>
          <DealTypePref data={dealTypePref} />
        </div>
      </div>

      {/* BD Pattern Theses */}
      {Array.isArray(theses) && theses.length > 0 && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h3 style={{ margin: "0 0 0.75rem", fontSize: "0.95rem" }}>BD Strategy Theses</h3>
          <BDTheses data={theses} />
        </div>
      )}

      {/* Sunk Cost by TA */}
      {sunkCost && Object.keys(sunkCost).length > 0 && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h3 style={{ margin: "0 0 0.75rem", fontSize: "0.95rem" }}>
            Investment by Therapeutic Area
          </h3>
          <SunkCostMap data={sunkCost} />
        </div>
      )}

      {/* Scalar Fields */}
      <div className="card">
        <h3 style={{ margin: "0 0 1rem", fontSize: "0.95rem" }}>Profile Details</h3>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
            gap: "0.6rem",
            fontSize: "0.85rem",
          }}
        >
          {SCALAR_FIELDS.map(([label, dbCol]) => (
            <EditableField
              key={dbCol}
              label={label}
              value={String(buyer[dbCol] ?? "")}
              onSave={(v) => handleFieldSave(dbCol, v)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

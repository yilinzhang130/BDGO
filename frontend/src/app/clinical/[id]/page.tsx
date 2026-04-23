"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchClinicalRecord, updateRecord, deleteRecord } from "@/lib/api";
import { phaseBadgeClass, resultBadgeClass } from "@/lib/utils";
import { EditableField } from "@/components/ui/EditableField";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ReportButton } from "@/components/ui/ReportButton";
import { useAuth } from "@/components/AuthProvider";

interface Section {
  title: string;
  fields: [string, string][]; // [label, dbCol]
  defaultOpen?: boolean;
}

const SECTIONS: Section[] = [
  {
    title: "Trial Identity",
    defaultOpen: true,
    fields: [
      ["Trial ID", "试验ID"],
      ["Asset", "资产名称"],
      ["Company", "公司名称"],
      ["Indication", "适应症"],
      ["Phase", "临床期次"],
      ["Design", "试验设计类型"],
      ["Enrollment", "总入组人数"],
      ["Line", "线数"],
      ["Population", "入选人群"],
    ],
  },
  {
    title: "Primary Endpoint",
    defaultOpen: true,
    fields: [
      ["Definition", "主要终点定义"],
      ["Endpoint Name", "主要终点名称"],
      ["Result Value", "主要终点结果值"],
      ["Unit", "主要终点单位"],
      ["HR", "主要终点_HR"],
      ["p-value", "主要终点_p值"],
      ["CI 95%", "主要终点_CI95"],
      ["Met?", "主要终点达成"],
    ],
  },
  {
    title: "Secondary Endpoints",
    fields: [
      ["Secondary EP 1", "次要终点1名称"],
      ["EP 1 Value", "次要终点1结果值"],
      ["EP 1 Unit", "次要终点1单位"],
      ["Secondary EP 2", "次要终点2名称"],
      ["EP 2 Value", "次要终点2结果值"],
      ["EP 2 Unit", "次要终点2单位"],
      ["Secondary EP 3", "次要终点3名称"],
      ["EP 3 Value", "次要终点3结果值"],
      ["EP 3 Unit", "次要终点3单位"],
    ],
  },
  {
    title: "Arms & Dosing",
    fields: [
      ["Arm Name", "臂名称"],
      ["Arm Type", "臂类型"],
      ["Arm Enrollment", "臂入组人数"],
      ["Dosing Regimen", "给药方案"],
    ],
  },
  {
    title: "Safety",
    fields: [
      ["Grade 3+ AE %", "Gr3plus_AE_pct"],
      ["AE Discontinuation %", "AE_discontinue_pct"],
      ["Key AE Description", "关键AE描述"],
      ["Safety Flag", "安全性标志"],
    ],
  },
  {
    title: "Assessment",
    defaultOpen: true,
    fields: [
      ["Clinical Score", "临床综合评分"],
      ["Result", "结果判定"],
      ["Regulatory Path", "监管路径"],
      ["Assessment Summary", "白袍评估摘要"],
      ["Data Status", "数据状态"],
      ["Data Cutoff", "数据截止日期"],
      ["Median Follow-up (mo)", "中位随访月数"],
      ["Analysis Population", "分析人群"],
    ],
  },
  {
    title: "Catalysts",
    fields: [
      ["Next Catalyst", "下一个催化剂"],
      ["Catalyst Type", "催化剂类型"],
      ["Expected Date", "催化剂预计时间"],
      ["Certainty", "催化剂确定性"],
    ],
  },
  {
    title: "Source & Tracking",
    fields: [
      ["Source File", "来源文件"],
      ["Source Link", "来源链接"],
      ["Data Source", "数据来源"],
      ["Notes", "备注"],
      ["Tracking", "追踪状态"],
      ["Assessment Date", "评估日期"],
      ["Raw Efficacy", "原始疗效文本"],
      ["Raw Endpoints", "原始终点结果"],
      ["Raw Design", "原始试验设计"],
      ["Raw Arms", "原始arms文本"],
    ],
  },
];

export default function ClinicalDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const id = decodeURIComponent(params.id as string);
  const isAdmin = user?.is_admin === true;

  const [record, setRecord] = useState<any>(null);
  const [notFound, setNotFound] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    SECTIONS.forEach((s) => {
      init[s.title] = s.defaultOpen ?? false;
    });
    return init;
  });

  useEffect(() => {
    fetchClinicalRecord(id)
      .then(setRecord)
      .catch(() => setNotFound(true));
  }, [id]);

  if (notFound) return <div className="loading">Clinical record not found</div>;
  if (!record) return <div className="loading">Loading...</div>;

  const handleFieldSave = async (dbCol: string, newValue: string) => {
    await updateRecord("临床", id, { [dbCol]: newValue });
    setRecord({ ...record, [dbCol]: newValue });
  };

  const handleDelete = async () => {
    await deleteRecord("临床", id);
    router.push("/clinical");
  };

  const toggleSection = (title: string) => {
    setOpenSections((prev) => ({ ...prev, [title]: !prev[title] }));
  };

  return (
    <div>
      <div className="detail-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <h1 style={{ margin: 0 }}>{record["试验ID"] || id}</h1>
              <ReportButton entityType="临床" entityKey={record["试验ID"] || id} />
            </div>
            <div className="meta">
              {record["公司名称"] && (
                <span
                  style={{ cursor: "pointer", textDecoration: "underline" }}
                  onClick={() =>
                    router.push(`/companies/${encodeURIComponent(record["公司名称"])}`)
                  }
                >
                  {record["公司名称"]}
                </span>
              )}
              {record["资产名称"] && <span>{record["资产名称"]}</span>}
              {record["临床期次"] && (
                <span className={`badge ${phaseBadgeClass(record["临床期次"])}`}>
                  {record["临床期次"]}
                </span>
              )}
              {record["结果判定"] && (
                <span className={`badge ${resultBadgeClass(record["结果判定"])}`}>
                  {record["结果判定"]}
                </span>
              )}
              {record["数据状态"] && <span>{record["数据状态"]}</span>}
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

      {SECTIONS.map((section) => (
        <div key={section.title} className="card" style={{ marginBottom: "0.75rem" }}>
          <h3
            onClick={() => toggleSection(section.title)}
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
                gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
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
                    value={String(record[dbCol] ?? "")}
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
                        color: record[dbCol] ? "var(--text)" : "var(--text-secondary)",
                      }}
                    >
                      {record[dbCol] || "\u2014"}
                    </span>
                  </div>
                ),
              )}
            </div>
          )}
        </div>
      ))}

      {showDelete && (
        <ConfirmDialog
          message={`Delete clinical record "${record["试验ID"] || id}"?`}
          onConfirm={handleDelete}
          onCancel={() => setShowDelete(false)}
        />
      )}
    </div>
  );
}

"use client";

import { useState, useRef } from "react";
import { uploadBP, runTask, fetchTaskStatus } from "@/lib/api";

interface Props {
  company?: string;
  onClose: () => void;
  onUploaded?: (filename: string) => void;
}

type Stage = "upload" | "uploaded" | "analyzing" | "done" | "failed";

export function BPUpload({ company, onClose, onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [stage, setStage] = useState<Stage>("upload");
  const [result, setResult] = useState<any>(null);
  const [analysisStatus, setAnalysisStatus] = useState("");
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    const ext = f.name.split(".").pop()?.toLowerCase();
    if (!["pdf", "pptx", "ppt", "docx", "doc"].includes(ext || "")) {
      setError("Unsupported file type. Please upload PDF, PPTX, or DOCX.");
      return;
    }
    setFile(f);
    setError("");
  };

  const handleUpload = async () => {
    if (!file) { setError("No file selected"); return; }
    setUploading(true);
    setError("");
    try {
      const res = await uploadBP(file, company);
      setResult(res);
      setStage("uploaded");
      if (onUploaded) onUploaded(res.filename);
    } catch (e: any) {
      setError(e.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const pollAnalysis = async (taskId: string) => {
    try {
      const status = await fetchTaskStatus(taskId);
      setAnalysisStatus(status.status);
      if (status.status === "completed") {
        setStage("done");
        return;
      }
      if (status.status === "failed" || status.status === "timeout") {
        setStage("failed");
        setError(status.error || "Analysis failed");
        return;
      }
      setTimeout(() => pollAnalysis(taskId), 3000);
    } catch {
      setStage("failed");
      setError("Failed to check analysis status");
    }
  };

  const handleAnalyze = async () => {
    if (!result) return;
    setStage("analyzing");
    setAnalysisStatus("queued");
    try {
      const { task_id } = await runTask("company_analyst", `@分析 ${result.filename}`);
      setTimeout(() => pollAnalysis(task_id), 2000);
    } catch (e: any) {
      setStage("failed");
      setError(e.message || "Failed to start analysis");
    }
  };

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ background: "var(--bg-card)", borderRadius: 12, padding: "1.5rem", maxWidth: 480, width: "90%", boxShadow: "0 8px 32px rgba(0,0,0,0.2)" }}
      >
        <h3 style={{ margin: "0 0 1rem", fontSize: "1rem" }}>
          Upload Business Plan {company ? `for ${company}` : "(New Company)"}
        </h3>

        {stage === "upload" && (
          <>
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
              }}
              style={{
                border: `2px dashed ${dragOver ? "var(--accent)" : "var(--border)"}`,
                borderRadius: 8, padding: "2rem", textAlign: "center",
                background: dragOver ? "var(--accent-light)" : "var(--bg)", marginBottom: "1rem", transition: "all 0.2s",
              }}
            >
              {file ? (
                <div>
                  <div style={{ fontSize: "0.95rem", fontWeight: 600 }}>{file.name}</div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </div>
                </div>
              ) : (
                <div style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "0.75rem" }}>
                  Drop a file here, or choose below
                </div>
              )}
              <label
                style={{
                  display: "inline-block", padding: "0.5rem 1.2rem", background: "var(--accent)",
                  color: "white", borderRadius: 6, cursor: "pointer", fontSize: "0.85rem", fontWeight: 600,
                }}
              >
                {file ? "Change File" : "Choose File"}
                <input
                  ref={inputRef}
                  type="file"
                  accept=".pdf,.pptx,.ppt,.docx,.doc"
                  style={{ display: "none" }}
                  onChange={(e) => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }}
                />
              </label>
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.5rem" }}>
                PDF, PPTX, DOCX supported
              </div>
            </div>

            {error && <div style={{ color: "var(--red)", fontSize: "0.85rem", marginBottom: "0.75rem" }}>{error}</div>}

            <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
              <button onClick={onClose} style={{ padding: "0.45rem 1rem", border: "1px solid var(--border)", borderRadius: 6, background: "var(--bg-card)", cursor: "pointer", fontSize: "0.85rem" }}>
                Cancel
              </button>
              <button
                onClick={handleUpload}
                disabled={!file || uploading}
                style={{ padding: "0.45rem 1rem", border: "none", borderRadius: 6, background: file ? "var(--accent)" : "#94a3b8", color: "white", cursor: file ? "pointer" : "not-allowed", fontSize: "0.85rem", fontWeight: 600 }}
              >
                {uploading ? "Uploading..." : "Upload"}
              </button>
            </div>
          </>
        )}

        {stage === "uploaded" && (
          <div style={{ textAlign: "center", padding: "1rem 0" }}>
            <div style={{ fontSize: "2rem", marginBottom: "0.5rem", color: "#10b981" }}>&#10003;</div>
            <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>Upload Successful</div>
            <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "1.5rem" }}>{result.filename}</div>
            <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center" }}>
              <button
                onClick={handleAnalyze}
                style={{ padding: "0.5rem 1.2rem", border: "none", borderRadius: 6, background: "#8b5cf6", color: "white", cursor: "pointer", fontSize: "0.85rem", fontWeight: 600 }}
              >
                Run AI Analysis
              </button>
              <button onClick={onClose} style={{ padding: "0.45rem 1rem", border: "1px solid var(--border)", borderRadius: 6, background: "var(--bg-card)", cursor: "pointer", fontSize: "0.85rem" }}>
                Skip
              </button>
            </div>
          </div>
        )}

        {stage === "analyzing" && (
          <div style={{ textAlign: "center", padding: "2rem 0" }}>
            <div style={{ fontSize: "1.5rem", marginBottom: "0.75rem", animation: "spin 2s linear infinite" }}>&#9696;</div>
            <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>AI Analysis Running</div>
            <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              Status: {analysisStatus}
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.5rem" }}>
              This may take 10-20 minutes. You can close this dialog — analysis will continue in the background.
            </div>
            <button onClick={onClose} style={{ marginTop: "1rem", padding: "0.45rem 1rem", border: "1px solid var(--border)", borderRadius: 6, background: "var(--bg-card)", cursor: "pointer", fontSize: "0.85rem" }}>
              Close (runs in background)
            </button>
          </div>
        )}

        {stage === "done" && (
          <div style={{ textAlign: "center", padding: "2rem 0" }}>
            <div style={{ fontSize: "2rem", marginBottom: "0.5rem", color: "#10b981" }}>&#10003;</div>
            <div style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Analysis Complete</div>
            <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
              Data has been analyzed and ingested into the CRM.
            </div>
            <button onClick={onClose} style={{ padding: "0.45rem 1rem", border: "none", borderRadius: 6, background: "var(--accent)", color: "white", cursor: "pointer", fontSize: "0.85rem", fontWeight: 600 }}>
              Done
            </button>
          </div>
        )}

        {stage === "failed" && (
          <div style={{ textAlign: "center", padding: "1rem 0" }}>
            <div style={{ fontSize: "2rem", marginBottom: "0.5rem", color: "var(--red)" }}>&#10007;</div>
            <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>Analysis Failed</div>
            {error && <div style={{ fontSize: "0.85rem", color: "var(--red)", marginBottom: "1rem" }}>{error}</div>}
            <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center" }}>
              <button onClick={handleAnalyze} style={{ padding: "0.45rem 1rem", border: "none", borderRadius: 6, background: "#8b5cf6", color: "white", cursor: "pointer", fontSize: "0.85rem", fontWeight: 600 }}>
                Retry
              </button>
              <button onClick={onClose} style={{ padding: "0.45rem 1rem", border: "1px solid var(--border)", borderRadius: 6, background: "var(--bg-card)", cursor: "pointer", fontSize: "0.85rem" }}>
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

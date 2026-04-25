"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { BPUpload } from "@/components/ui/BPUpload";

export default function UploadPage() {
  const router = useRouter();
  const [showUpload, setShowUpload] = useState(true);
  const [lastUploaded, setLastUploaded] = useState<string | null>(null);

  const handleSuggestedCommand = (command: string) => {
    try {
      sessionStorage.setItem("bdgo.chat.prefill", command);
    } catch {
      // sessionStorage may be unavailable (SSR/private mode); fall through
    }
    router.push("/chat");
  };

  return (
    <div>
      <div className="page-header">
        <h1>Upload & Analyze</h1>
      </div>

      <div className="card" style={{ maxWidth: 600 }}>
        <h3 style={{ margin: "0 0 0.75rem", fontSize: "0.95rem" }}>Upload Business Plan</h3>
        <p style={{ margin: "0 0 1rem", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          Upload a BP file (PDF/PPTX) to analyze a new company. The AI agent will automatically
          analyze the document and ingest the data into the database.
        </p>
        <button
          onClick={() => setShowUpload(true)}
          style={{
            padding: "0.5rem 1.2rem",
            background: "#8b5cf6",
            color: "white",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: "0.85rem",
            fontWeight: 600,
          }}
        >
          Upload New BP
        </button>
        {lastUploaded && (
          <div
            style={{ marginTop: "0.75rem", fontSize: "0.85rem", color: "var(--text-secondary)" }}
          >
            Last uploaded: <strong>{lastUploaded}</strong>
          </div>
        )}
      </div>

      {showUpload && (
        <BPUpload
          onClose={() => setShowUpload(false)}
          onUploaded={(filename) => setLastUploaded(filename)}
          onSuggestedCommand={handleSuggestedCommand}
        />
      )}
    </div>
  );
}

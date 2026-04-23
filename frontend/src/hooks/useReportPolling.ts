"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchReportStatus, generateReport } from "@/lib/api";
import { addCompletedReport } from "@/lib/reports";
import type { ReportService, ReportStage, ReportStartInfo } from "@/components/ui/report/types";

/**
 * Owns the report-generation lifecycle: form → running → done/error.
 * Submits the job, polls status every 2s, persists completed reports
 * to localStorage, and surfaces error messages (shared between form
 * validation and fatal post-submit failures).
 */
export function useReportPolling({
  service,
  params,
  onStarted,
}: {
  service: ReportService;
  params: Record<string, any>;
  onStarted?: (info: ReportStartInfo) => void;
}) {
  const [stage, setStage] = useState<ReportStage>("form");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progressLog, setProgressLog] = useState<string[]>([]);
  const [result, setResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (stage !== "running" || !taskId) return;
    let alive = true;

    const poll = async () => {
      try {
        const status = await fetchReportStatus(taskId);
        if (!alive) return;

        const nextLog = status.progress_log || [];
        setProgressLog((prev) =>
          prev.length === nextLog.length && prev.every((line, i) => line === nextLog[i])
            ? prev
            : nextLog,
        );

        if (status.status === "completed") {
          setResult(status.result);
          setStage("done");
          const title = deriveTitle(service, params, status.result?.meta || {});
          addCompletedReport({
            taskId,
            slug: service.slug,
            displayName: service.display_name,
            title,
            markdownPreview: (status.result?.markdown || "").slice(0, 500),
            files: status.result?.files || [],
            meta: status.result?.meta || {},
            createdAt: Date.now(),
          });
          return;
        }
        if (status.status === "failed") {
          setErrorMsg(status.error || "Report generation failed");
          setStage("error");
          return;
        }
        setTimeout(poll, 2000);
      } catch (e: any) {
        setErrorMsg(e.message || "Status check failed");
        setStage("error");
      }
    };

    setTimeout(poll, 1500);
    return () => {
      alive = false;
    };
  }, [stage, taskId, service, params]);

  const submit = useCallback(async () => {
    const required = service.input_schema.required || [];
    for (const field of required) {
      if (!params[field]) {
        setErrorMsg(`Missing required field: ${field}`);
        return;
      }
    }
    setErrorMsg(null);
    try {
      const resp = await generateReport(service.slug, params);
      setTaskId(resp.task_id);
      if (onStarted) {
        onStarted({
          task_id: resp.task_id,
          slug: service.slug,
          estimated_seconds: service.estimated_seconds,
          params,
        });
        return;
      }
      if (resp.status === "completed") {
        setResult(resp.result);
        setStage("done");
      } else {
        setStage("running");
      }
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to start");
      setStage("error");
    }
  }, [service, params, onStarted]);

  const retry = useCallback(() => {
    setErrorMsg(null);
    setStage("form");
  }, []);

  return { stage, taskId, progressLog, result, errorMsg, submit, retry };
}

function deriveTitle(service: ReportService, params: any, meta: any): string {
  if (meta.title) return meta.title;
  if (meta.topic) return meta.topic;
  if (params.topic) return params.topic;
  if (params.pmid) return `PMID ${params.pmid}`;
  if (params.doi) return params.doi;
  if (params.filename) return params.filename;
  return service.display_name;
}

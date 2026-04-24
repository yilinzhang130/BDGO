"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchReportStatus, generateReport, type TaskStatusResponse } from "@/lib/api";
import { addCompletedReport } from "@/lib/reports";
import type { ReportService, ReportStage, ReportStartInfo } from "@/components/ui/report/types";

type ReportResult = TaskStatusResponse["result"];

function errorMessage(e: unknown, fallback: string): string {
  if (e instanceof Error) return e.message;
  return fallback;
}

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
  params: Record<string, unknown>;
  onStarted?: (info: ReportStartInfo) => void;
}) {
  const [stage, setStage] = useState<ReportStage>("form");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progressLog, setProgressLog] = useState<string[]>([]);
  const [result, setResult] = useState<ReportResult>(undefined);
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
      } catch (e) {
        setErrorMsg(errorMessage(e, "Status check failed"));
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
    } catch (e) {
      setErrorMsg(errorMessage(e, "Failed to start"));
      setStage("error");
    }
  }, [service, params, onStarted]);

  const retry = useCallback(() => {
    setErrorMsg(null);
    setStage("form");
  }, []);

  return { stage, taskId, progressLog, result, errorMsg, submit, retry };
}

function deriveTitle(
  service: ReportService,
  params: Record<string, unknown>,
  meta: Record<string, unknown>,
): string {
  if (typeof meta.title === "string" && meta.title) return meta.title;
  if (typeof meta.topic === "string" && meta.topic) return meta.topic;
  if (typeof params.topic === "string" && params.topic) return params.topic;
  if (typeof params.pmid === "string" && params.pmid) return `PMID ${params.pmid}`;
  if (typeof params.doi === "string" && params.doi) return params.doi;
  if (typeof params.filename === "string" && params.filename) return params.filename;
  return service.display_name;
}

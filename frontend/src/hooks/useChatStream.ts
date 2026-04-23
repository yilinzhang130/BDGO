"use client";

import { useCallback, useState } from "react";
import { chatStream, type PlanConfirmPayload, type PlanMode, type SearchMode } from "@/lib/api";
import { applyCreditsUsage, getSelectedModel, refreshCredits } from "@/lib/credits";
import {
  autoTitleFromFirstMessage,
  type ContextEntity,
  type PlanProposal,
  type QuickSearchSource,
  useSessionStore,
} from "@/lib/sessions";
import { parseSSEStream, type SSEEvent } from "@/lib/sseStream";

export interface StreamIntoOpts {
  targetSessionId: string;
  assistantMsgId: string;
  message: string;
  files: string[];
  planModeOverride: PlanMode;
  planConfirm?: PlanConfirmPayload;
  searchModeOverride?: SearchMode;
}

/**
 * Wraps `chatStream` + SSE parsing. Routes each event into the session
 * store and exposes a single `isStreaming` flag for the UI to disable
 * inputs.
 */
export function useChatStream() {
  const {
    appendAssistantChunk,
    addToolEvent,
    addReportTask,
    setMessagePlan,
    setMessageQuickSources,
    setMessageError,
    addContextEntity,
    markMessageDone,
  } = useSessionStore();

  const [isStreaming, setIsStreaming] = useState(false);

  const streamInto = useCallback(
    async (opts: StreamIntoOpts) => {
      const {
        targetSessionId,
        assistantMsgId,
        message,
        files,
        planModeOverride,
        planConfirm,
        searchModeOverride,
      } = opts;
      setIsStreaming(true);
      let errored = false;
      const failWith = (msg: string) => {
        errored = true;
        setMessageError(targetSessionId, assistantMsgId, msg);
      };

      const handleEvent = (data: SSEEvent) => {
        if (data.type === "chunk") {
          appendAssistantChunk(targetSessionId, assistantMsgId, data.content as string);
        } else if (data.type === "tool_call") {
          addToolEvent(targetSessionId, assistantMsgId, {
            type: "tool_call",
            name: data.name as string,
          });
        } else if (data.type === "tool_result") {
          addToolEvent(targetSessionId, assistantMsgId, {
            type: "tool_result",
            name: data.name as string,
          });
        } else if (data.type === "report_task") {
          addReportTask(targetSessionId, assistantMsgId, {
            task_id: data.task_id as string,
            slug: data.slug as string,
            estimated_seconds: data.estimated_seconds as number,
          });
        } else if (data.type === "plan_proposal") {
          setMessagePlan(
            targetSessionId,
            assistantMsgId,
            data.plan as PlanProposal,
            (data.original_message as string) || message,
          );
        } else if (data.type === "quick_sources") {
          setMessageQuickSources(
            targetSessionId,
            assistantMsgId,
            (data.sources as QuickSearchSource[]) || [],
          );
        } else if (data.type === "context_entity") {
          const entity: ContextEntity = {
            id: data.id as string,
            entityType: data.entity_type as ContextEntity["entityType"],
            title: data.title as string,
            subtitle: data.subtitle as string | undefined,
            fields: (data.fields as ContextEntity["fields"]) || [],
            href: data.href as string | undefined,
            addedAt: Date.now(),
          };
          addContextEntity(targetSessionId, entity);
        } else if (data.type === "error") {
          failWith((data.message as string) || "未知错误");
        } else if (data.type === "usage") {
          applyCreditsUsage(
            (data.credits_charged as number) ?? 0,
            (data.balance as number) ?? null,
          );
        } else if (data.type === "done") {
          markMessageDone(targetSessionId, assistantMsgId);
          void refreshCredits();
        }
      };

      try {
        const res = await chatStream(
          message,
          targetSessionId,
          files,
          getSelectedModel() || undefined,
          planModeOverride,
          planConfirm,
          searchModeOverride ?? "agent",
        );
        await parseSSEStream(res, handleEvent);
      } catch (e: unknown) {
        const msg = (e as Error)?.message || "";
        failWith(
          msg.includes("credit") || msg.includes("402")
            ? msg
            : "网络连接失败，请检查网络后点击重试。",
        );
      } finally {
        setIsStreaming(false);
        if (!errored) {
          markMessageDone(targetSessionId, assistantMsgId);
        }
        autoTitleFromFirstMessage(targetSessionId);
      }
    },
    [
      appendAssistantChunk,
      addToolEvent,
      addReportTask,
      setMessagePlan,
      setMessageQuickSources,
      setMessageError,
      addContextEntity,
      markMessageDone,
    ],
  );

  return { streamInto, isStreaming };
}

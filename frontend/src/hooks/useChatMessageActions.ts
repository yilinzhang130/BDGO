"use client";

import { useCallback } from "react";
import type { PlanMode, SearchMode } from "@/lib/api";
import { useSessionStore } from "@/lib/sessions";
import type { StreamIntoOpts } from "@/hooks/useChatStream";

/**
 * Per-message callbacks rendered inside ChatMessage: retry, plan confirm /
 * skip / cancel. They all share the same "kill old assistant msg, spin up
 * a fresh one, stream into it" pattern, so they're bundled.
 */
export function useChatMessageActions(
  streamInto: (opts: StreamIntoOpts) => Promise<void>,
  {
    isStreaming,
    planMode,
    searchMode,
  }: { isStreaming: boolean; planMode: PlanMode; searchMode: SearchMode },
) {
  const { active, activeId, addMessage, removeMessage, updatePlanStatus } = useSessionStore();

  const spawnAssistantPlaceholder = useCallback(
    (sessionId: string): string => {
      const id = crypto.randomUUID().slice(0, 12);
      addMessage(sessionId, {
        id,
        role: "assistant",
        content: "",
        tools: [],
        streaming: true,
        createdAt: Date.now(),
      });
      return id;
    },
    [addMessage],
  );

  const handleRetry = useCallback(
    async (erroredMsgId: string) => {
      if (!activeId || isStreaming || !active) return;
      const idx = active.messages.findIndex((m) => m.id === erroredMsgId);
      if (idx <= 0) return;
      let userIdx = idx - 1;
      while (userIdx >= 0 && active.messages[userIdx].role !== "user") userIdx--;
      if (userIdx < 0) return;
      const userMsg = active.messages[userIdx];

      removeMessage(activeId, erroredMsgId);
      const assistantMsgId = spawnAssistantPlaceholder(activeId);

      await streamInto({
        targetSessionId: activeId,
        assistantMsgId,
        message: userMsg.content,
        files: userMsg.attachments || [],
        planModeOverride: planMode,
        searchModeOverride: searchMode,
      });
    },
    [
      activeId,
      active,
      isStreaming,
      removeMessage,
      spawnAssistantPlaceholder,
      streamInto,
      planMode,
      searchMode,
    ],
  );

  const handlePlanConfirm = useCallback(
    async (planMsgId: string, selectedStepIds: string[]) => {
      if (!activeId) return;
      const planMsg = active?.messages.find((m) => m.id === planMsgId);
      if (!planMsg || !planMsg.plan || !planMsg.originalMessage) return;

      const selectedSteps = planMsg.plan.steps
        .filter((s) => selectedStepIds.includes(s.id) || s.required)
        .map((s) => ({
          id: s.id,
          title: s.title,
          description: s.description,
          tools_expected: s.tools_expected,
        }));

      updatePlanStatus(
        activeId,
        planMsgId,
        "confirmed",
        selectedSteps.map((s) => s.id),
      );
      const executionMsgId = spawnAssistantPlaceholder(activeId);

      await streamInto({
        targetSessionId: activeId,
        assistantMsgId: executionMsgId,
        message: planMsg.originalMessage,
        files: [],
        planModeOverride: "off",
        planConfirm: {
          plan_id: planMsg.plan.plan_id,
          plan_title: planMsg.plan.title,
          selected_steps: selectedSteps,
          original_message: planMsg.originalMessage,
        },
      });
    },
    [activeId, active, updatePlanStatus, spawnAssistantPlaceholder, streamInto],
  );

  const handlePlanSkip = useCallback(
    async (planMsgId: string) => {
      if (!activeId) return;
      const planMsg = active?.messages.find((m) => m.id === planMsgId);
      if (!planMsg || !planMsg.originalMessage) return;

      updatePlanStatus(activeId, planMsgId, "cancelled");
      const executionMsgId = spawnAssistantPlaceholder(activeId);

      await streamInto({
        targetSessionId: activeId,
        assistantMsgId: executionMsgId,
        message: planMsg.originalMessage,
        files: [],
        planModeOverride: "off",
      });
    },
    [activeId, active, updatePlanStatus, spawnAssistantPlaceholder, streamInto],
  );

  const handlePlanCancel = useCallback(
    (planMsgId: string) => {
      if (!activeId) return;
      updatePlanStatus(activeId, planMsgId, "cancelled");
    },
    [activeId, updatePlanStatus],
  );

  return { handleRetry, handlePlanConfirm, handlePlanSkip, handlePlanCancel };
}

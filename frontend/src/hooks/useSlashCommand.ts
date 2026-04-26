"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchReportServices, generateReport, parseReportArgs } from "@/lib/api";
import { autoTitleFromFirstMessage, useSessionStore } from "@/lib/sessions";
import { SLASH_COMMANDS, type SlashCommand } from "@/components/ui/SlashCommandPopup";
import type { ReportService } from "@/components/ui/report/types";

export interface ReportStartInfo {
  task_id: string;
  slug: string;
  estimated_seconds: number;
  params: Record<string, unknown>;
}

/**
 * Slash-command state + report dispatch.
 *
 * Claude-style flow: picking a command from the popup drops `/alias `
 * into the input so the user can describe the job in natural language.
 * On send the LLM parses the args and either fires the report or posts
 * a chat message listing what's still missing — no modal form.
 */
export function useSlashCommand(getInput: () => string, setInput: (v: string) => void) {
  const { activeId, addMessage, addReportTask, markMessageDone } = useSessionStore();

  const [reportServices, setReportServices] = useState<ReportService[]>([]);
  const [slashActiveIndex, setSlashActiveIndex] = useState(0);
  const [slashParsing, setSlashParsing] = useState(false);
  // Services-fetch state. Previously this was a fire-and-forget call with
  // `.catch(() => {})` swallowing every error — when /api/reports/list
  // failed (CORS / 401 / 500 / network), the slash popup silently degraded
  // to slug-only display and clicks did nothing. Now the failure surfaces:
  //   - console.warn so it's visible in devtools immediately
  //   - servicesLoadError is exposed to consumers (chat page can render a
  //     banner / inline notice based on it)
  //   - retryLoadServices() lets the UI offer a "Retry" button
  //   - Auto-retry with backoff: 3 attempts then give up
  const [servicesLoadError, setServicesLoadError] = useState<string | null>(null);
  const [servicesLoading, setServicesLoading] = useState(true);

  const loadServices = useCallback(async (): Promise<void> => {
    // Iterative retry loop (avoids self-referencing useCallback). Three
    // attempts with exponential backoff — 0ms, 800ms, 2400ms.
    setServicesLoading(true);
    let lastError: string | null = null;
    for (let attempt = 0; attempt < 3; attempt++) {
      if (attempt > 0) {
        const delay = 800 * Math.pow(3, attempt - 1);
        await new Promise((r) => setTimeout(r, delay));
      }
      try {
        const data = (await fetchReportServices()) as { services?: ReportService[] };
        const services = data?.services || [];
        setReportServices(services);
        setServicesLoadError(null);
        setServicesLoading(false);
        if (services.length === 0) {
          // Endpoint reachable but returned no services — server-side
          // misconfiguration. Surface as a soft warning.
          console.warn("/api/reports/list returned 0 services; slash commands may not work");
        }
        return;
      } catch (e) {
        const detail = e instanceof Error ? e.message : String(e);
        lastError = detail;
        console.warn(
          `[useSlashCommand] fetchReportServices failed (attempt ${attempt + 1}/3): ${detail}`,
        );
      }
    }
    setServicesLoadError(lastError || "Failed to load report services after 3 attempts");
    setServicesLoading(false);
  }, []);

  useEffect(() => {
    void loadServices();
  }, [loadServices]);

  const slashCommandsAll = useMemo<SlashCommand[]>(
    () =>
      SLASH_COMMANDS.map((base) => {
        const svc = reportServices.find((s) => s.slug === base.slug);
        return {
          alias: base.alias,
          slug: base.slug,
          displayName: svc?.display_name || base.slug,
          description: svc?.description || "",
          example: base.example,
          estimatedSeconds: svc?.estimated_seconds,
        };
      }),
    [reportServices],
  );

  const pushAssistantMessage = useCallback(
    (content: string) => {
      if (!activeId) return;
      const id = crypto.randomUUID().slice(0, 12);
      addMessage(activeId, {
        id,
        role: "assistant",
        content,
        tools: [],
        streaming: false,
        createdAt: Date.now(),
      });
      markMessageDone(activeId, id);
    },
    [activeId, addMessage, markMessageDone],
  );

  const handleReportStarted = useCallback(
    (info: ReportStartInfo) => {
      if (!activeId) return;
      const svc = reportServices.find((s) => s.slug === info.slug);
      const displayName = svc?.display_name || info.slug;

      const paramSummary = Object.entries(info.params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "" && v !== false)
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");

      const userMsgId = crypto.randomUUID().slice(0, 12);
      const assistantMsgId = crypto.randomUUID().slice(0, 12);

      addMessage(activeId, {
        id: userMsgId,
        role: "user",
        content: `生成 ${displayName}${paramSummary ? `（${paramSummary}）` : ""}`,
        createdAt: Date.now(),
      });
      addMessage(activeId, {
        id: assistantMsgId,
        role: "assistant",
        content: `正在生成 **${displayName}**，完成后会附下载链接。`,
        tools: [],
        streaming: false,
        createdAt: Date.now(),
      });
      addReportTask(activeId, assistantMsgId, {
        task_id: info.task_id,
        slug: info.slug,
        estimated_seconds: info.estimated_seconds,
      });
      markMessageDone(activeId, assistantMsgId);
      autoTitleFromFirstMessage(activeId);
    },
    [activeId, reportServices, addMessage, addReportTask, markMessageDone],
  );

  const parseAndRun = useCallback(
    async (svc: ReportService, cmd: SlashCommand, rest: string) => {
      if (activeId) {
        const userMsgId = crypto.randomUUID().slice(0, 12);
        addMessage(activeId, {
          id: userMsgId,
          role: "user",
          content: `/${cmd.alias} ${rest}`,
          createdAt: Date.now(),
        });
        autoTitleFromFirstMessage(activeId);
      }

      setSlashParsing(true);
      try {
        const parsed = await parseReportArgs(cmd.slug, rest);
        if (parsed.complete) {
          const resp = (await generateReport(cmd.slug, parsed.params)) as { task_id: string };
          const assistantMsgId = crypto.randomUUID().slice(0, 12);
          if (activeId) {
            addMessage(activeId, {
              id: assistantMsgId,
              role: "assistant",
              content: `正在生成 **${svc.display_name}**，完成后会附下载链接。`,
              tools: [],
              streaming: false,
              createdAt: Date.now(),
            });
            addReportTask(activeId, assistantMsgId, {
              task_id: resp.task_id,
              slug: cmd.slug,
              estimated_seconds: svc.estimated_seconds ?? 60,
            });
            markMessageDone(activeId, assistantMsgId);
          }
          return;
        }

        const missingFields = parsed.missing || [];
        const missing = missingFields.join("、") || "更多信息";
        const partial = Object.entries(parsed.params || {})
          .filter(([, v]) => v !== undefined && v !== null && v !== "")
          .map(([k, v]) => `${k}: ${v}`)
          .join("，");
        const partialHint = partial ? `\n\n已识别：${partial}` : "";

        // Quick-patch hint: build a kv-style template the user can copy-paste
        // and fill inline. The backend kv-parser (PR #123) takes these
        // deterministically with no LLM round-trip, so iterating on missing
        // fields is fast even for /draft-X services with 10+ params.
        const kvQuickPatch = missingFields.length
          ? `\n\n直接粘贴补全（每个 \`key="value"\`）：\n\`/${cmd.alias} ${missingFields
              .map((f) => `${f}="…"`)
              .join(" ")}\``
          : "";

        pushAssistantMessage(
          `生成 **${svc.display_name}** 还缺少：**${missing}**。${partialHint}${kvQuickPatch}\n\n或用自由文本，例如：\`/${cmd.alias} ${cmd.example}\``,
        );
      } catch (e) {
        const msg = e instanceof Error ? e.message : "未知错误";
        pushAssistantMessage(`解析 \`/${cmd.alias}\` 参数失败：${msg}`);
      } finally {
        setSlashParsing(false);
      }
    },
    [activeId, addMessage, addReportTask, markMessageDone, pushAssistantMessage],
  );

  const handleSlashSelect = useCallback(
    async (cmd: SlashCommand) => {
      const svc = reportServices.find((s) => s.slug === cmd.slug);
      if (!svc) {
        setInput(`/${cmd.alias} `);
        return;
      }

      const current = getInput();
      const rest = current.startsWith("/")
        ? current
            .slice(1)
            .replace(/^\S+\s*/, "")
            .trim()
        : "";

      if (!rest) {
        const typedAlias = current.startsWith("/") ? current.slice(1).split(/\s/)[0] : "";
        if (typedAlias !== cmd.alias) {
          setInput(`/${cmd.alias} `);
          return;
        }
        setInput("");
        pushAssistantMessage(
          `**${svc.display_name}** — ${svc.description || "生成报告"}\n\n在 \`/${cmd.alias}\` 后用一句话描述需要什么，例如：\`/${cmd.alias} ${cmd.example}\``,
        );
        return;
      }

      setInput("");
      await parseAndRun(svc, cmd, rest);
    },
    [reportServices, getInput, setInput, parseAndRun, pushAssistantMessage],
  );

  return {
    slashCommandsAll,
    slashActiveIndex,
    setSlashActiveIndex,
    slashParsing,
    handleSlashSelect,
    handleReportStarted,
    // Services-fetch lifecycle — let the UI surface failures rather than
    // silently degrading to slug-only slash commands.
    servicesLoading,
    servicesLoadError,
    retryLoadServices: loadServices,
  };
}

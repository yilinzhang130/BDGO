"""
BD Synthesize — read multiple completed report tasks and produce a single
comprehensive BD strategy memo.

Designed primarily as the final "synthesis" step of a BD intake plan
(after target / disease / IP / evaluate / mnc / timing all complete),
but is generic — works on any set of completed tasks the calling user
owns.

Pipeline:
  1. For each task_id, look up report_history (filtered to ctx.user_id)
  2. Parse files_json → find the .md file → read it from disk
  3. Truncate per-report to a per-source budget so total LLM context
     stays bounded
  4. Single LLM call → BD strategy memo (markdown)
  5. Render .md + .docx, return ReportResult

Security:
  - Only includes task_ids owned by ctx.user_id (silently skips others)
  - Only reads tasks with status="completed"
  - Hard-fails if ctx.user_id is None (auth required)

Output sections:
  1. 资产定位（一句话）
  2. BD 可能性评分 + 摘要
  3. 推荐 deal 结构 + 估值锚点
  4. Top-3 买方匹配 + 各自 fit 理由
  5. 关键风险 top-3
  6. 推荐时间窗口
  7. 下一步 action（chips）
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any

from auth_db import transaction
from config import REPORTS_DIR
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

from services.document import docx_builder
from services.quality import audit_to_dict, validate_markdown
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import safe_slug

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────


# Per-source markdown char budget — caps each source so total LLM input
# stays bounded even if user passes 10 task_ids of long reports.
_PER_SOURCE_CHARS = 6000

# Maximum task_ids accepted in one synthesis call. Synthesizing more than
# this is rare and likely a sign of misuse.
_MAX_TASK_IDS = 10


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class SynthesizeInput(BaseModel):
    task_ids: list[str] = Field(
        ...,
        min_length=2,
        max_length=_MAX_TASK_IDS,
        description="task_ids of prior completed reports to synthesize.",
    )
    asset_name: str | None = Field(None, description="Asset name for headline / personalization.")
    company: str | None = Field(None, description="Company name for headline.")
    focus: str | None = Field(
        None,
        description="Free-text focus, e.g. '重点看 Top-3 买方排序' or 'highlight IP risks'.",
    )


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """你是 BD Go 的资深 BD 总监。任务：读取一组已完成的 BD 调研报告（可能包括靶点分析、疾病 landscape、IP 检查、资产吸引力评估、买方匹配、时机建议等），综合成一份**BD 策略备忘**。

## 硬规则

1. **只输出 markdown**，无 JSON、无围栏整体内容。
2. **每条结论必须有依据**：引用源报告中的具体数据 / 章节。禁止凭空编造数字、买方名字、deal 条款。
3. **数据 > 形容词**：禁用「巨大潜力」、「广阔前景」。每个判断必须配数字、时间、或具体事件。
4. **中英双语**：中文为主，金额/术语/数据保留英文（如 "$8.5B TAM"、"Phase 2 ORR 38%"、"upfront $50M / total $800M"）。
5. **不替代法律 / 投资意见**：不做"买入 / 卖出"建议，做"BD 决策辅助"。
6. **禁止 hallucinate 源报告里没有的内容**：如果某个章节缺乏支撑，写"⚠️ 源报告缺少 X 数据"而不是编造。

## 输出结构（严格按此 7 节）

```
# BD 策略备忘 — {company} {asset_name}

> **生成日期**: {today}  ·  **依据**: {n_sources} 份调研报告

## 一、资产定位（一句话）
（≤ 30 字）一句话说清楚：靶点 + 阶段 + positioning（FIC/BIC/Me-too/Generic）+ 主适应症

## 二、BD 可能性评分
- 综合评分（如有 /evaluate 报告则引用其分数）：⭐⭐⭐⭐ / 5
- 一段话理由（≤ 150 字），引用 /evaluate 关键论点

## 三、推荐 Deal 结构
- 推荐结构：License / Co-Dev / Out-license / 其他
- 估值锚点：upfront $X-XM / total $X-XB（引用可比交易）
- 一段话说明为什么这个结构

## 四、Top-3 买方匹配
| Rank | Buyer | 为什么 fit | Outreach 优先级 |
|---|---|---|---|
| 1 | ... | （3-5 句话；引用买方近期 deal、TA 重点、pipeline gap） | High/Med/Low |
| 2 | ... | ... | ... |
| 3 | ... | ... | ... |

如源报告未给出买方推荐 → 标注「⚠️ 买方匹配信息不足」。

## 五、关键风险 Top-3
1. **风险标题** — 描述（≤ 50 字）+ 来源等级（L1 文本/L2 推断/L3 情境/L4 外部）
2. ...
3. ...

来源：从 /ip / /evaluate / /target / /disease 等报告里提炼。

## 六、推荐时间窗口
（如有 /timing 报告则引用具体窗口；否则给一般性建议）
- 最优窗口：YYYY-MM-DD 至 YYYY-MM-DD
- 理由：1 句话

## 七、下一步 Action
列 3-5 个具体 next steps，每个含：
- 行动（cold outreach / 进一步调研 / 准备 teaser）
- 触发条件（"如果 buyer X 回复" / "在 catalyst Y 之前"）
- 时限（"本周内" / "P2 readout 前 8 周"）
```

## 写作风格

- 不写"建议您"、"我方建议"、"接下来可以"——直接陈述结论
- 每节如果源报告没有相关内容，明确写「源报告未涉及」而不是省略
"""


USER_PROMPT_TEMPLATE = """## 综合分析任务

- **资产**: {asset_label}
- **聚焦**: {focus}
- **今天**: {today}

## 源报告（共 {n_sources} 份）

{sources_block}

## 任务

按系统提示的 7 节结构生成 BD 策略备忘 markdown。直接以 `# BD 策略备忘 — {asset_label}` 开头。
"""


_GAP_FILL_PROMPT = """以下是已生成的 BD 策略备忘 markdown 草稿，以及 Schema 校验器发现的结构性缺陷列表。
请在**不改变已通过校验内容**的前提下，仅修补以下缺陷，输出**完整的修正后 markdown**。

=== 待修补缺陷 ===
{fail_list}

=== 原始 markdown ===
{markdown}

修补规则：
- "section_missing" → 按 7 节顺序（资产定位 / BD 评分 / Deal 结构 / Top-3 买方 / 风险 / 时间 / 下一步）插入缺失节
- Top-3 买方节必须含 Rank 1, 2, 3 三行（即使是占位符也要列出）；建议表格格式
- 关键风险节必须 ≥3 编号风险，每条带来源等级（L1/L2/L3/L4）
- 下一步 Action 节必须 ≥3 个具体行动（不要泛泛"持续关注"）
- 不要新增未列出的章节，不要删除已有内容
- 数据驱动 — 引用源报告的具体数字 / 章节，不要 hallucinate
- 输出整个 markdown，不加任何解释或代码块包裹
"""


def _build_gap_fill_prompt(markdown: str, audit) -> str:
    fail_lines = [
        f"[{f.section}] {f.message}" + (f" | 证据: {f.evidence}" if f.evidence else "")
        for f in audit.findings
        if f.severity == "fail"
    ]
    return _GAP_FILL_PROMPT.format(
        fail_list="\n".join(f"- {line}" for line in fail_lines),
        markdown=markdown[:60_000],
    )


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class BDSynthesizeService(ReportService):
    slug = "bd-synthesize"
    display_name = "BD Strategy Synthesize"
    description = (
        "综合多份 BD 调研报告（靶点 / 疾病 / IP / 资产评估 / 买方 / 时机等）"
        "成一份策略备忘。BD intake 流程的最终综合 step；也可单独使用。"
    )
    chat_tool_name = "synthesize_bd_memo"
    chat_tool_description = (
        "Read 2-10 completed BD report tasks (by task_id) owned by the calling "
        "user and produce a single BD strategy memo synthesizing them. Used as "
        "the final step of a BD intake plan, but generic — works on any "
        "combination of report task_ids. Returns .md + .docx, ~30-50s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "task_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": _MAX_TASK_IDS,
                "description": "task_ids of prior completed reports.",
            },
            "asset_name": {"type": "string"},
            "company": {"type": "string"},
            "focus": {"type": "string"},
        },
        "required": ["task_ids"],
    }
    input_model = SynthesizeInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 40
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = SynthesizeInput(**params)

        if not ctx.user_id:
            raise RuntimeError("BD synthesis requires an authenticated user.")

        today = datetime.date.today().isoformat()

        # Phase 1 — Load source reports (filtered by user_id + completed)
        ctx.log(f"Loading {len(inp.task_ids)} source reports…")
        sources = self._load_sources(ctx.user_id, inp.task_ids)
        if len(sources) < 2:
            raise RuntimeError(
                f"Need at least 2 completed reports to synthesize; got {len(sources)}. "
                f"Check task_ids belong to current user and are completed."
            )
        ctx.log(
            f"Loaded {len(sources)} reports ({sum(len(s['markdown']) for s in sources)} chars total)"
        )

        # Phase 2 — Build sources block
        sources_block = self._format_sources_block(sources)
        asset_label = self._asset_label(inp)

        # Phase 3 — LLM synthesis
        ctx.log("LLM: synthesizing BD strategy memo…")
        user_prompt = USER_PROMPT_TEMPLATE.format(
            asset_label=asset_label,
            focus=inp.focus or "(无)",
            today=today,
            n_sources=len(sources),
            sources_block=sources_block,
        )
        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=3500,
        )
        if not markdown or len(markdown) < 500:
            raise RuntimeError("LLM produced an empty or too-short synthesis.")

        # Phase 4 — L0/L1 schema validation + targeted gap-fill
        # Synthesis is the deciding output of an /intake plan: missing
        # sections (especially Top-3 buyers or risks) directly degrade
        # downstream BD decisions. Run one repair pass before saving.
        schema_audit, markdown = self._validate_and_repair(markdown, ctx)

        # Phase 5 — Save outputs (post-repair)
        slug = safe_slug(asset_label) or "synthesis"
        md_filename = f"bd_memo_{slug}_{today}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown saved")

        ctx.log("Rendering Word document…")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"BD 策略备忘 — {asset_label}",
            subtitle=f"综合 {len(sources)} 份报告 · {today}",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(f"bd_memo_{slug}_{today}.docx", docx_bytes, format="docx")

        suggested_commands = self._build_suggested_commands(inp, sources)

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"BD Strategy Memo — {asset_label}",
                "asset": inp.asset_name,
                "company": inp.company,
                "n_sources": len(sources),
                "source_slugs": [s["slug"] for s in sources],
                "schema_audit": schema_audit,
                "suggested_commands": suggested_commands,
            },
        )

    # ── L0 + L1 quality pass ────────────────────────────────

    def _validate_and_repair(self, markdown: str, ctx: ReportContext) -> tuple[dict, str]:
        """Schema audit; if FAIL>0, one targeted gap-fill LLM pass.

        Mirrors /draft-ts and /dataroom pattern. Never raises — validation
        failure must not block delivery.
        """
        try:
            audit = validate_markdown(markdown, mode="bd_synthesize")
            ctx.log(f"Schema audit: FAIL={audit.n_fail} WARN={audit.n_warn} INFO={audit.n_info}")
            if audit.n_fail == 0:
                return audit_to_dict(audit), markdown

            ctx.log(f"L1 gap-fill: {audit.n_fail} fail(s) — targeted patch…")
            patched = ctx.llm(
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_gap_fill_prompt(markdown, audit)}],
                max_tokens=4000,
                label="synthesize_gap_fill",
            )
            if len(patched) > 500:
                audit2 = validate_markdown(patched, mode="bd_synthesize")
                ctx.log(
                    f"Post-gap-fill audit: FAIL={audit2.n_fail} "
                    f"WARN={audit2.n_warn} (was {audit.n_fail} fail)"
                )
                if audit2.n_fail < audit.n_fail:
                    schema_audit = audit_to_dict(audit2)
                    schema_audit["gap_fill_attempted"] = True
                    schema_audit["gap_fill_fail_before"] = audit.n_fail
                    schema_audit["gap_fill_fail_after"] = audit2.n_fail
                    return schema_audit, patched

                ctx.log("L1 gap-fill didn't reduce FAILs — keeping original")
            else:
                ctx.log("L1 gap-fill produced too-short output — keeping original")

            schema_audit = audit_to_dict(audit)
            schema_audit["gap_fill_attempted"] = True
            schema_audit["gap_fill_fail_before"] = audit.n_fail
            return schema_audit, markdown
        except Exception:
            logger.exception("Schema validation failed for task %s", ctx.task_id)
            return {"error": "validator_exception"}, markdown

    # ── Source loading ──────────────────────────────────────

    def _load_sources(self, user_id: str, task_ids: list[str]) -> list[dict[str, Any]]:
        """Load report_history rows + .md file contents for the given task_ids.

        Returns only completed tasks owned by user_id. Skips silently otherwise.
        Each returned dict: {task_id, slug, title, markdown, meta}.
        """
        if not task_ids:
            return []

        # Use ANY(%s) for IN-style query with parameterized list (psycopg2-friendly)
        with transaction() as cur:
            cur.cursor_factory = RealDictCursor
            cur.execute(
                """
                SELECT task_id, slug, title, files_json, meta_json, status
                FROM report_history
                WHERE user_id = %s::uuid
                  AND task_id = ANY(%s)
                  AND status = 'completed'
                ORDER BY created_at ASC
                """,
                (user_id, task_ids),
            )
            rows = cur.fetchall()

        sources: list[dict[str, Any]] = []
        for row in rows:
            md_text = self._read_task_markdown(row["task_id"], row.get("files_json"))
            if not md_text:
                logger.info("synthesize: skipping task_id=%s — no .md file", row["task_id"])
                continue
            try:
                meta = json.loads(row.get("meta_json") or "{}")
            except (json.JSONDecodeError, TypeError):
                meta = {}
            sources.append(
                {
                    "task_id": row["task_id"],
                    "slug": row["slug"],
                    "title": row.get("title") or row["slug"],
                    "markdown": md_text[:_PER_SOURCE_CHARS],
                    "truncated": len(md_text) > _PER_SOURCE_CHARS,
                    "meta": meta,
                }
            )
        return sources

    def _read_task_markdown(self, task_id: str, files_json: str | None) -> str:
        """Pick the .md file for this task_id and read it from disk.

        Strategy: parse files_json → find the first .md → read REPORTS_DIR/{task_id}/{filename}.
        If files_json is absent or parsing fails, glob the directory for *.md.
        """
        candidate: Path | None = None
        if files_json:
            try:
                files = json.loads(files_json)
                for f in files:
                    if isinstance(f, dict) and f.get("format") == "md" and f.get("filename"):
                        candidate = REPORTS_DIR / task_id / f["filename"]
                        break
            except (json.JSONDecodeError, TypeError):
                pass

        if candidate is None or not candidate.exists():
            # Last resort: scan the task directory for any *.md
            task_dir = REPORTS_DIR / task_id
            if task_dir.is_dir():
                md_files = sorted(task_dir.glob("*.md"))
                if md_files:
                    candidate = md_files[0]

        if candidate is None or not candidate.exists():
            return ""
        try:
            return candidate.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("synthesize: failed to read %s: %s", candidate, e)
            return ""

    # ── Prompt formatting ───────────────────────────────────

    def _asset_label(self, inp: SynthesizeInput) -> str:
        if inp.company and inp.asset_name:
            return f"{inp.company} / {inp.asset_name}"
        return inp.asset_name or inp.company or "(unspecified asset)"

    def _format_sources_block(self, sources: list[dict[str, Any]]) -> str:
        chunks = []
        for i, s in enumerate(sources, 1):
            header = (
                f"### [来源 {i}] {s['title']}\n- 服务: `{s['slug']}` · task_id: `{s['task_id']}`"
            )
            if s["truncated"]:
                header += f" · ⚠️ 已截断到 {_PER_SOURCE_CHARS} 字"
            chunks.append(f"{header}\n\n{s['markdown']}")
        return "\n\n---\n\n".join(chunks)

    # ── Lifecycle handoff chips ─────────────────────────────

    def _build_suggested_commands(
        self, inp: SynthesizeInput, sources: list[dict[str, Any]]
    ) -> list[dict]:
        """After synthesis → primary next action is outreach to top buyer.

        We can't reliably extract "top buyer" from the synthesis output here
        (would require parsing markdown). So suggest /email + /timing as
        generic chips and let the user fill in the buyer.
        """
        chips: list[dict] = []
        # If we know the asset+company, the email chip is more useful with
        # asset_context pre-filled
        asset_ctx = ""
        if inp.asset_name:
            asset_ctx = inp.asset_name
            # Try to extract indication from a source meta if available
            for s in sources:
                ind = s["meta"].get("indication")
                if ind:
                    asset_ctx = f"{inp.asset_name} — {ind}"
                    break

        email_parts = [
            '/email to_company="<top buyer name>"',
            " purpose=cold_outreach",
            " from_perspective=seller",
        ]
        if asset_ctx:
            email_parts.append(f' asset_context="{asset_ctx}"')
        chips.append(
            {
                "label": "Draft Cold Outreach (fill buyer)",
                "command": "".join(email_parts),
                "slug": "outreach-email",
            }
        )

        if inp.company:
            chips.append(
                {
                    "label": "Check Outreach Timing",
                    "command": (
                        f'/timing company_name="{inp.company}"'
                        + (f' asset_name="{inp.asset_name}"' if inp.asset_name else "")
                        + " perspective=seller"
                    ),
                    "slug": "timing-advisor",
                }
            )

        return chips

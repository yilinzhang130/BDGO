"""
BD Legal Review — port of the local ``bd-legal-review`` skill.

Review four BD contract stages — CDA / TS / MTA / DA (License / Co-Dev / SPA) —
from a BD/IP commercial-risk lens. Evidence-chained, four-tier source
classification (L1 textual / L2 inferred / L3 conditional / L4 external),
anti-dramatic, with negotiation-priority output (P0 / P1 / P2).

This is **not** legal counsel. The output report carries an explicit
disclaimer; users are instructed to have qualified counsel review before
signing. The value is in catching commercial asymmetry, combination-risk
chains, and ambiguous definitions that lawyers may pass over.

Pipeline:
  1. Resolve contract text (uploaded file in BP_DIR via filename, or pasted
     text via contract_text)
  2. Truncate to a safe LLM-context budget if oversized
  3. Build a per-type system prompt + user prompt
  4. Single MiniMax call to produce the full markdown review
  5. Save markdown + render styled .docx via docx_builder
  6. Return both files for download
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from config import BP_DIR
from pydantic import BaseModel, model_validator

from services.document import docx_builder
from services.document.contract_extract import extract_contract_text
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import safe_slug

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Input schema
# ─────────────────────────────────────────────────────────────


_CONTRACT_TYPE_NAMES = {
    "cda": "CDA / NDA（保密协议）",
    "ts": "Term Sheet / LOI",
    "mta": "MTA（Material Transfer Agreement）",
    "license": "License Agreement（许可协议）",
    "co_dev": "Co-Development Agreement（共同开发协议）",
    "spa": "SPA / Merger（股权收购 / 合并协议）",
}


class LegalReviewInput(BaseModel):
    contract_type: Literal["cda", "ts", "mta", "license", "co_dev", "spa"]
    party_position: Literal["甲方", "乙方"]
    contract_text: str | None = None
    filename: str | None = None  # uploaded file in BP_DIR
    counterparty: str | None = None
    project_name: str | None = None
    focus: str | None = None  # 自由文本，e.g. "重点看 IP 转移和排他"

    @model_validator(mode="after")
    def _require_text_or_filename(self) -> LegalReviewInput:
        if not self.contract_text and not self.filename:
            raise ValueError("必须提供 contract_text（粘贴文本）或 filename（上传文件名）之一")
        return self


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

# A safe budget for raw contract text in the LLM call. Beyond this we
# truncate and tell the user. License / SPA can run to 200+ pages; we
# trade fidelity for fitting in context. 80k chars ≈ 30-50k tokens.
_MAX_CONTRACT_CHARS = 80_000


SYSTEM_PROMPT_BASE = """你是资深 BD/IP 商业条款审查官，服务于 biotech 跨境交易。

你的核心任务**不是**替代律师出具法律意见，而是从商业风险视角识别合同里的**权利义务非对称、组合效应陷阱、条款歧义**，并用**原文证据链**支撑每一个结论。

## 风险来源四级分类（必须执行）

每一条结论必须明确标注来源等级：

- **L1 文本确定** — 字面含义明确：表述为「Section X 规定 Y」
- **L2 合理推断** — 字面未明说，但体系可推导：「按此条款效果，Z 场景下可能产生 W 风险」
- **L3 情境假设** — 需特定场景成立才构成风险：「若发生 X，则 Y」
- **L4 外部依赖** — 需合同外事实成立：「此风险取决于 XX 事实」

**L2-L4 结论禁止使用「确定风险」、「必然」、「一定」等词汇**。

## 绝对禁令

1. **禁止戏剧化词汇**：不得使用「掠夺性」、「锁死」、「陷阱」、「致命」、「deal breaker」，除非每次使用前能给出 L1 级原文依据
2. **禁止无证据结论**：任何「风险」、「限制」、「义务」表述必须配原文引用（Section 号 + 关键短语）
3. **禁止推断性扩大解读**：定义范围严格以合同内定义为准；未定义词汇必须标注「此词在合同中未定义」
4. **禁止只看坏消息**：必须同样呈现对我方有利的条款或惯例水平内容
5. **禁止替代法律意见**：报告必须含免责声明

## 主动扫描的四类组合风险链

单条条款往往不致命，风险藏在组合里：

1. **IP 转移链**：披露义务 → 使用范围 → 许可授予 → 排他承诺
2. **提前终止陷阱链**：终止权 → 存续条款 → 锁定期
3. **财务收割链**：费用安排 → 审计权 → 税收让渡 → 赔偿
4. **管辖救济陷阱链**：管辖地 → 转让权 → 担保陈述 → 赔偿上限

## 自我反驳（生成前内部完成）

对每个风险结论，先内部回答：
1. 字面依据：能找到直接支持的句子吗？→ 分级 L1-L4
2. 语气污染：戏剧化词汇是否回到原文有强度？
3. 单条 vs 组合：是否把单条效应夸大到整份合同？
4. 极端 vs 典型：「最长 X 月」≠「通常 X 月」
5. 定义范围：是否扩大了合同内定义？
6. 对称性：是否只看了不利条款？

无法通过的结论必须删除或降级。

## 输出报告结构（严格遵守）

直接以 markdown 输出，使用以下章节：

```
# {合同标识} 审查意见

## 一、免责声明
（醒目段落，明确这不是律师法律意见、签署前须由具备跨境技术交易经验的合格法律顾问 review）

## 二、执行摘要
- 总体判断（1-2 段）
- 按优先级的建议行动一览（P0/P1/P2 计数）

## 三、确定风险（L1 级）
每节按以下结构：
- **风险编号** R-01
- **原文**（引用块，注明 Section/Article 号）
- **条款效果**（字面含义）
- **对我方影响**
- **建议处理**（替代措辞或谈判方向）

## 四、条款歧义（L2-L3 级）
- 列出每种解读及依据
- 建议通过补充条款或 confirming email 固化

## 五、谈判路径建议
- **P0 必谈**：影响高 × 让步概率中高 — 表格列出，含理想版/底线版替代措辞
- **P1 强烈建议**：影响中 × 让步概率中，或影响高 × 让步概率低但必须争取
- **P2 清洁化**：影响低但措辞可精确

## 六、签署前 Checklist
- 必做事项列表（执业律师 review、税务顾问、IP 盘点、BD 历史核查、预算匹配等）

## 七、结论-证据映射表（必须包含）

| 结论编号 | 风险描述 | 原文依据 | 来源等级 | 情境假设 | 商业影响 |
|---|---|---|---|---|---|
| R-01 | ... | Section X.Y: "..." | L1 | 无 | 高 |

## 八、签署建议
- 总体建议：可签 / 有条件签 / 建议重大修改 / 不建议签
- 后续关注点
```
"""


_TYPE_CHECKLISTS = {
    "cda": """
## CDA / NDA 必查清单

- [ ] **单向 vs 双向**：MNC 模板常单向（只保护 MNC 信息）→ 必须争取双向
- [ ] **机密信息定义**：标记为 Confidential 才算？还是 reasonably expected to be confidential 也算？口头披露需否书面确认？
- [ ] **Non-Use 承诺**：仅「不披露」不够，必须同时约定「不使用于本次评估目的以外」
- [ ] **Residuals Clause**：「员工记住的信息可自由使用」= 变相技术转移，必须删除或限定
- [ ] **保密期限**：通常 2-5 年；超 7 年警惕；IP 类信息应设合同后持续保密
- [ ] **排除项完整性**：public domain / independent development / third party disclosure 是否齐全？有无「receiving party determines is not confidential」自定义排除（红旗）
- [ ] **披露豁免**：是否含向投资人 / DD / 融资方 / 审计师 / 律师披露的豁免？
- [ ] **返还/销毁义务**：有效期届满或终止后信息如何处理？
- [ ] **管辖地**：中立仲裁（HKIAC / SIAC）优先；对方主场专属法院 = 红旗
- [ ] **救济条款**：Injunctive relief 是否保留？

### 典型红旗
- ⚠️ Residuals Clause（员工大脑记住的信息）
- ⚠️ 单向保密 + 我方披露义务
- ⚠️ 无 Non-Use 承诺
- ⚠️ CI 需书面标注才受保护
- ⚠️ 排除项过宽（自定义排除）
- ⚠️ 保密期限 > 7 年
- ⚠️ 披露豁免仅含税务机关（投资人 DD 无法披露）

### 行业惯例
- 保密期 2-5 年；IP 类设合同后持续义务
- 单向 CDA：可接受前提是我方无需披露任何 CI
- 管辖：HKIAC / SIAC / ICC 均可接受
""",
    "ts": """
## TS / LOI 必查清单

- [ ] **Binding vs Non-Binding 划分**：哪些 binding（保密、排他、费用、管辖）？哪些 non-binding（交易条款）？
- [ ] **排他期（No-Shop）**：通常 30-90 天
- [ ] **Break-up Fee**：金额、触发条件、哪方支付
- [ ] **Cost Allocation**：DD 费用、法律费用分担
- [ ] **Expiration**：TS 本身有效期

### 典型红旗
- ⚠️ 长排他期（>90 天）
- ⚠️ Non-Binding 伪装 Binding（含 「good faith negotiation」可起诉条款）
- ⚠️ Expense Reimbursement 过宽
""",
    "mta": """
## MTA 必查清单

- [ ] **Material 定义**：精确范围？包括 derivatives / modifications / progeny？
- [ ] **使用目的**：严格限定 Research Project？有无 「for any purpose」？
- [ ] **衍生物归属**：使用 Material 产生的新物质/数据归谁？
- [ ] **Know-How 披露义务**：「足以完成项目」还是「足以独立复现」？后者是红旗
- [ ] **发表限制**：审阅时限？回应期？延期上限？「不得无理拒绝」？
- [ ] **保密定义对称性**：双向还是单向？单向 + 披露义务 = IP 非对称的主要信号
- [ ] **排他承诺**：not to license to third parties？期限？
- [ ] **材料销毁义务**：项目结束后是否要求销毁？

### 典型红旗
- ⚠️ 「for any purpose」使用权（MTA 夹带 License 的信号）
- ⚠️ Sole Invention 归对方
- ⚠️ 永久免费 Know-How 许可（fully paid-up / worldwide / royalty-free / sublicensable 组合）
- ⚠️ 单向保密 + 披露义务
- ⚠️ 披露至「可复现」程度（实质技术转移）

### IP 转移链组合（必须主动扫描）
披露义务（至 reproduce/use in own research）→ 使用权（for any purpose）→ 许可（fully paid-up, worldwide, royalty-free, sublicensable）→ 排他（shall not enter into agreement with third parties）= 此 MTA 实质是 License。

### 行业惯例
- ROFN Option Period: 3-12 个月；Negotiation Period: 3-6 个月
- 保密期 5-10 年；销毁义务 30-90 天
""",
    "license": """
## License Agreement 必查清单

- [ ] **Licensed Technology/IP 定义**：许可对象精确范围
- [ ] **Field 定义**：是否过宽（all therapeutic uses）或过窄
- [ ] **Territory**：独占 / 共同独占 / 非独占
- [ ] **Sublicense 权**：是否允许？需否同意？同意门槛？经济分成？
- [ ] **Diligence 义务**：CRE 是否有量化里程碑？
- [ ] **里程碑支付**：触发条件清晰？是否多适应症/多地域重复支付？
- [ ] **Royalty**：税率、Stacking Cap、Know-How Tail、Anti-stacking 保护
- [ ] **审计权**：频次、回溯期、差异阈值（通常 5%）
- [ ] **Grant-Back**：反向 License 范围？是否独占？
- [ ] **Improvement**：许可期内改进归谁？
- [ ] **终止后权利**：Licensee 是否保留数据/IP？已付款项是否退还？
- [ ] **变更控制**：Control Change 后 License 自动转让/终止？

### 典型红旗
- ⚠️ 过宽 Field（all indications + all therapeutic uses）
- ⚠️ 模糊 CRE 标准（无量化定义）
- ⚠️ 单边 Sublicense 权
- ⚠️ 过高 Royalty Stacking（实际到手 <20%）
- ⚠️ 过长 Know-How Tail（专利过期后仍付 10+ 年）
- ⚠️ Improvement 自动许可（反向技术转移）
- ⚠️ Grant-Back 过宽（免费反授所有相关研发）

### 行业惯例
- Upfront：IND 前 $1-10M；IND 后 $5-50M
- 里程碑：小分子 $50-500M；生物药 $100M-1B+
- Royalty：tiered 5-20%（基于 Net Sales）
- Grant-Back 限「许可技术本身的直接改进」
""",
    "co_dev": """
## Co-Development 必查清单

- [ ] **JSC 决策机制**：组成、投票权、tie-breaker
- [ ] **成本分摊**：比例、超支处理、退出选项
- [ ] **IP 归属**：Sole Invention / Joint Invention
- [ ] **Opt-out 权**：权利转换（通常变 Royalty-bearing License）
- [ ] **Buy-out / Buy-in**：估值机制
- [ ] **地域分工**：跨地域协作机制
- [ ] **Diligence 义务**：双方是否都有？

### 典型红旗
- ⚠️ JSC 僵局一方单边决定
- ⚠️ Opt-out 门槛过高（exit fee 或 cooling period 过长）
- ⚠️ IP 归属一边倒（Joint Invention 实质一方主导）
- ⚠️ 成本分摊与商业化权利不对称
""",
    "spa": """
## SPA / Merger 必查清单

- [ ] **R&W 范围**：覆盖 IP / 员工 / 税务 / 合规 / 合同 / 诉讼 / 环保？
- [ ] **Survival Period**：一般 R&W 12-24 个月；Fundamental 更长或无限期
- [ ] **Indemnification**：Cap（一般 10-20%，Fundamental 100%）/ Basket（0.5-1%）/ Threshold
- [ ] **Escrow / Holdback**：比例 10-15%，期限 12-18 个月
- [ ] **R&W 保险**：是否使用？覆盖范围？
- [ ] **MAC 定义**：是否 carve-out COVID / war / market-wide？
- [ ] **Closing Conditions**：客观性，避免 satisfactory to Buyer 主观条款
- [ ] **Interim Operating Covenants**：签约到交割之间的经营限制
- [ ] **No-Shop / Go-Shop**：期限、违约金
- [ ] **Non-Compete / Non-Solicit**：期限（2-5 年）、地域、业务范围

### 典型红旗
- ⚠️ Fundamental R&W 过宽（一般性 R&W 列为 Fundamental 享 100% cap）
- ⚠️ MAC loopholes（无 carve-out，Buyer 借市场波动终止）
- ⚠️ 主观性 Closing Conditions（satisfactory to Buyer in its sole discretion）
- ⚠️ Special Indemnity 过宽
- ⚠️ Earnout 陷阱（目标由 Buyer 控制的变量决定）

### 行业惯例
- R&W 保险：Premium 2.5-4%，coverage 10%
- Cap：10-20%（一般）/ 100%（Fundamental）
- Basket：0.5-1%
- Survival：12-24 月（一般）/ 3-6 年（Fundamental）/ Indefinite（Tax / Authority / Ownership）
""",
}


_USER_PROMPT_TEMPLATE = """
## 本次审查信息

- **合同类型**：{contract_type_name}
- **我方立场**：{party_position}
- **对方**：{counterparty}
- **项目名称**：{project_name}
- **审查重点**：{focus}

## 合同原文

{truncation_note}

```
{contract_text}
```

请按系统提示要求生成完整 markdown 审查报告，从 `# {report_title}` 开头直接输出，不要加任何前言。
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class LegalReviewService(ReportService):
    slug = "legal-review"
    display_name = "BD 合同审查（CDA / TS / MTA / DA）"
    description = (
        "BD/IP 商业风险视角的合同条款审查。支持 CDA / TS / MTA / License / "
        "Co-Dev / SPA 六类合同。证据化、L1-L4 来源分级、反戏剧化。"
        "输出含原文引用的 Word 报告 + 谈判优先级（P0/P1/P2）+ 替代措辞。"
        "不替代律师法律意见。"
    )
    chat_tool_name = "generate_legal_review"
    chat_tool_description = (
        "Run a BD/IP commercial-risk review of a contract (CDA / NDA / Term Sheet / "
        "MTA / License / Co-Development / SPA / Merger). Returns a markdown + .docx "
        "report with L1-L4 source classification, asymmetry findings, combination "
        "risk chains, P0/P1/P2 negotiation priorities, and alternative wording. "
        "Provide either contract_text (pasted) or filename (uploaded under BP_DIR). "
        "This is NOT legal counsel — the report carries an explicit disclaimer."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "contract_type": {
                "type": "string",
                "enum": ["cda", "ts", "mta", "license", "co_dev", "spa"],
                "description": "Contract category. cda=CDA/NDA, ts=Term Sheet/LOI, mta=Material Transfer, license=License Agreement, co_dev=Co-Development, spa=Stock Purchase / Merger.",
            },
            "party_position": {
                "type": "string",
                "enum": ["甲方", "乙方"],
                "description": "我方在合同中的立场。",
            },
            "contract_text": {
                "type": "string",
                "description": "Pasted contract text. Either this or filename is required.",
            },
            "filename": {
                "type": "string",
                "description": "Uploaded contract file under BP_DIR (.pdf or .docx). Either this or contract_text is required.",
            },
            "counterparty": {
                "type": "string",
                "description": "Counterparty company name (optional, used in report header).",
            },
            "project_name": {
                "type": "string",
                "description": "Project / asset name (optional, used in report header).",
            },
            "focus": {
                "type": "string",
                "description": "Optional free-text focus areas, e.g. 'Focus on IP and exclusivity clauses'.",
            },
        },
        "required": ["contract_type", "party_position"],
    }
    input_model = LegalReviewInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 180
    category = "report"
    field_rules = {
        "contract_text": {"visible_when": {"filename": ""}},
        "filename": {"visible_when": {"contract_text": ""}},
    }

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = LegalReviewInput(**params)
        contract_text, source_label = self._resolve_contract_text(inp, ctx)
        if not contract_text.strip():
            raise RuntimeError(
                "无法读取合同文本：filename 文件不存在/不可解析，且 contract_text 为空。"
            )

        contract_text, truncated = self._truncate(contract_text)
        if truncated:
            ctx.log(f"合同正文超过 {_MAX_CONTRACT_CHARS} 字，已截断尾部以适配 LLM 上下文")

        contract_type_name = _CONTRACT_TYPE_NAMES[inp.contract_type]
        report_title = self._compose_title(inp, contract_type_name)

        ctx.log(f"调用 LLM 审查 {contract_type_name}...")
        markdown = self._call_llm(
            inp, contract_text, contract_type_name, report_title, truncated, ctx
        )

        if len(markdown) < 800:
            raise RuntimeError("LLM returned empty or very short legal review")

        slug = safe_slug(report_title)
        md_filename = f"legal_review_{slug}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown saved")

        ctx.log("Rendering Word document...")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc, title=report_title, subtitle=f"BD 合同审查 · {contract_type_name}"
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)

        docx_filename = f"legal_review_{slug}.docx"
        ctx.save_file(docx_filename, docx_bytes, format="docx")
        ctx.log("Word document saved")

        suggested_commands = self._build_suggested_commands(inp)

        meta: dict = {
            "title": report_title,
            "contract_type": inp.contract_type,
            "contract_type_name": contract_type_name,
            "party_position": inp.party_position,
            "counterparty": inp.counterparty or "",
            "project_name": inp.project_name or "",
            "source": source_label,
            "truncated": truncated,
            "input_chars": len(contract_text),
            "output_chars": len(markdown),
        }
        if suggested_commands:
            meta["suggested_commands"] = suggested_commands

        return ReportResult(markdown=markdown, meta=meta)

    # ── helpers ─────────────────────────────────────────────

    def _resolve_contract_text(self, inp: LegalReviewInput, ctx: ReportContext) -> tuple[str, str]:
        """Return (text, source_label). Prefers filename if both given."""
        if inp.filename:
            ctx.log(f"Extracting contract text from {inp.filename}...")
            filepath = BP_DIR / Path(inp.filename).name
            text = extract_contract_text(filepath)
            return text, f"file:{Path(inp.filename).name}"
        return (inp.contract_text or ""), "pasted"

    def _truncate(self, text: str) -> tuple[str, bool]:
        if len(text) <= _MAX_CONTRACT_CHARS:
            return text, False
        return text[:_MAX_CONTRACT_CHARS], True

    def _build_suggested_commands(self, inp: LegalReviewInput) -> list[dict]:
        """BD lifecycle next-step chips by contract type.

        Lifecycle flow:
          cda  → /dd (due diligence)
          ts   → /legal license | /legal co_dev  (definitive agreement)
          mta  → /legal license  (MTA is often a precursor to licensing)
          license / co_dev / spa → [] (end of lifecycle)
        """
        if inp.contract_type == "cda" and inp.counterparty:
            return [
                {
                    "label": "Run DD Checklist",
                    "command": f'/dd company="{inp.counterparty}"',
                    "slug": "dd-checklist",
                }
            ]

        if inp.contract_type == "ts":
            return self._ts_next_steps(inp)

        if inp.contract_type == "mta":
            return self._mta_next_steps(inp)

        # license / co_dev / spa — end of lifecycle, no further chip
        return []

    def _mta_next_steps(self, inp: LegalReviewInput) -> list[dict]:
        """After MTA review → offer the License Agreement (most common next step)."""
        parts = ["/legal contract_type=license", f' party_position="{inp.party_position}"']
        if inp.counterparty:
            parts.append(f' counterparty="{inp.counterparty}"')
        if inp.project_name:
            parts.append(f' project_name="{inp.project_name}"')
        return [
            {
                "label": "Draft License Agreement",
                "command": "".join(parts),
                "slug": "legal-review",
            }
        ]

    def _ts_next_steps(self, inp: LegalReviewInput) -> list[dict]:
        """After term sheet review → offer the two most common definitive agreements."""
        base = {
            "counterparty": f' counterparty="{inp.counterparty}"' if inp.counterparty else "",
            "project": f' project_name="{inp.project_name}"' if inp.project_name else "",
            "position": f' party_position="{inp.party_position}"',
        }

        def _cmd(contract_type: str) -> str:
            return (
                f"/legal contract_type={contract_type}"
                f"{base['position']}"
                f"{base['counterparty']}"
                f"{base['project']}"
            )

        return [
            {
                "label": "Draft License Agreement",
                "command": _cmd("license"),
                "slug": "legal-review",
            },
            {"label": "Draft Co-Dev Agreement", "command": _cmd("co_dev"), "slug": "legal-review"},
        ]

    def _compose_title(self, inp: LegalReviewInput, contract_type_name: str) -> str:
        parts = []
        if inp.counterparty:
            parts.append(inp.counterparty)
        if inp.project_name:
            parts.append(inp.project_name)
        if not parts:
            parts.append("合同")
        parts.append(contract_type_name.split("（")[0])
        parts.append("审查意见")
        return " — ".join(parts)

    def _call_llm(
        self,
        inp: LegalReviewInput,
        contract_text: str,
        contract_type_name: str,
        report_title: str,
        truncated: bool,
        ctx: ReportContext,
    ) -> str:
        system_prompt = SYSTEM_PROMPT_BASE + "\n\n" + _TYPE_CHECKLISTS[inp.contract_type]
        user_prompt = _USER_PROMPT_TEMPLATE.format(
            contract_type_name=contract_type_name,
            party_position=inp.party_position,
            counterparty=inp.counterparty or "（未提供）",
            project_name=inp.project_name or "（未提供）",
            focus=inp.focus or "全面审查（无特定重点）",
            truncation_note=(
                "> ⚠️ 合同正文已被截断（超过 LLM 上下文预算）；以下为前 80,000 字。"
                if truncated
                else ""
            ),
            contract_text=contract_text,
            report_title=report_title,
        )
        return ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=8000,
            label=f"legal_review/{inp.contract_type}",
        )

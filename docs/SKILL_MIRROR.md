# Skill Mirror — BDGO 报告服务 vs 本地 OpenClaw 技能

BDGO 的 **26 个** ReportService 中有 **9 个**是本地 OpenClaw 技能的**线上 Python 实现**。本地 SKILL.md 是 prompt 的"原稿"，迭代快；BDGO Python 文件是"工厂"，把 prompt 嵌入完整的报告生产流水线（CRM 查询 → web 增强 → LLM → docx 渲染）。

剩下 **17 个**线上独有服务直接长在 BDGO 里，没有本地镜像（生命周期工具、写作工具、合同起草工具等）。

本文档是这两套系统之间的**唯一真源**。当用户说"升级 X 技能"时，先读这里。

---

## 概念区分

| | 本地 SKILL.md（镜像源）| BDGO Python（线上）|
|---|---|---|
| 路径 | `~/.openclaw/skills/<name>/SKILL.md` | `api/services/reports/<name>.py` |
| 格式 | Markdown（含 YAML frontmatter）| Python 类（继承 `ReportService`）|
| 包含 | Prompt 设计、章节结构、字数、判定规则、schema 契约 | Prompt 块 + CRM 查询 + Tavily + ThreadPoolExecutor + docx 渲染 |
| 谁先变 | **本地总是先于线上**（你直接在 SKILL.md 上迭代）|
| 谁是消费方 | MiniMax agent（OpenClaw 平台）| FastAPI `/api/reports/generate`（BDGO 用户聊天里的 `/mnc` 等）|

---

## 镜像映射表（9 对）

| 斜杠 alias | slug | 本地 SKILL.md | 本地版本/最近改动 | 线上 Python 文件 | Prompt 锚点（行号 + 变量）|
|---|---|---|---|---|---|
| `/mnc` | `buyer-profile` | `mnc-buyer-profile/SKILL.md` (1435L) | **v0.2.1** / 2026-04-24 | [buyer_profile.py:54](../api/services/reports/buyer_profile.py) | `CHAPTER_SYSTEM_PROMPT` (L54) |
| `/commercial` | `commercial-assessment` | `commercial-assessment/SKILL.md` (566L) | 2026-04-15 | [commercial_assessment.py:55](../api/services/reports/commercial_assessment.py) | `SYSTEM_PROMPT` (L55) + `REPORT_PROMPT` |
| `/teaser` | `deal-teaser` | `deal-teaser-generator/SKILL.md` (327L) | 2026-04-15 | [deal_teaser.py:42](../api/services/reports/deal_teaser.py) | `SYSTEM_PROMPT` (L42) + `USER_PROMPT` |
| `/disease` | `disease-landscape` | `disease-landscape/SKILL.md` (469L) | 2026-04-15 | [disease_landscape.py:199](../api/services/reports/disease_landscape.py) | `CHAPTER_SYSTEM_PROMPT` (L199) + `_CH1_PROMPT` / `_CH2_PROMPT` ... |
| `/rnpv` | `rnpv-valuation` | `rnpv-valuation/SKILL.md` (523L) | 2026-04-24 | [rnpv_valuation.py:66](../api/services/reports/rnpv_valuation.py) | `SYSTEM_PROMPT` (L66) + `USER_PROMPT` |
| `/dd` | `dd-checklist` | `bd-dd-checklist/SKILL.md` (294L) | 2026-04-24 | [dd_checklist.py:209](../api/services/reports/dd_checklist.py) | `SYSTEM_PROMPT` (L209) + `_chapter_prompt` (L251) |
| `/evaluate` | `deal-evaluator` | `biotech-deal-asset-evaluator/SKILL.md` (684L) | 2026-04-24 | [deal_evaluator.py:44](../api/services/reports/deal_evaluator.py) | `SYSTEM_PROMPT` (L44) + `USER_PROMPT` |
| `/ip` | `ip-landscape` | `patent-landscape/SKILL.md` (712L) | 2026-04-24 | [ip_landscape.py:56](../api/services/reports/ip_landscape.py) | `CHAPTER_SYSTEM_PROMPT` (L56) + `_IP_CH1_PROMPT` / `_IP_CH2_PROMPT` ... |
| `/legal` | `legal-review` | `bd-legal-review/SKILL.md` | 2026-04-25 | [legal_review.py:86](../api/services/reports/legal_review.py) | `SYSTEM_PROMPT_BASE` (L86) + `_TYPE_CHECKLISTS` (L170) + `_USER_PROMPT_TEMPLATE` (L324) |

### 线上独有（无本地镜像，共 12 个）

这些 ReportService **没有**对应的 SKILL.md，prompt 直接长在 BDGO 里。

#### 早期单点工具（3 个）
| 斜杠 alias | slug | Python 文件 | 一句话说明 |
|---|---|---|---|
| `/paper` | `paper-analysis` | [paper_analysis.py](../api/services/reports/paper_analysis.py) | 文献综述（PubMed 检索 + LLM 综合） |
| `/target` | `target-radar` | [target_radar.py](../api/services/reports/target_radar.py) | 靶点 radar / 竞争格局 |
| `/guidelines` | `clinical-guidelines` | [clinical_guidelines.py](../api/services/reports/clinical_guidelines.py) | 临床治疗指南查询 |

如果要给这 3 个建立镜像，先在 `~/.openclaw/skills/` 下建 `SKILL.md`、把现有 Python prompt 拆出去、然后加进上面的镜像表。

#### BD Lifecycle 工具（8 个，2026-04-26 新增）
这一批是**生命周期编排 + 写作工具**，本质上不是分析报告，所以不需要本地 SKILL.md 镜像。

| 斜杠 alias | slug | Python 文件 | 用途 |
|---|---|---|---|
| `/company` | `company-analysis` | [company_analysis.py](../api/services/reports/company_analysis.py) | 公司深度分析（双向 buyer/seller/neutral；CRM + Web） |
| `/timing` | `timing-advisor` | [timing_advisor.py](../api/services/reports/timing_advisor.py) | Outreach 时机建议（CRM 催化剂 + 行业会议日历） |
| `/email` | `outreach-email` | [outreach_email.py](../api/services/reports/outreach_email.py) | Cold outreach email 草稿（双向，6 用途，中英双语） |
| `/log` | `outreach-log` | [outreach_log.py](../api/services/reports/outreach_log.py) | 记录 outreach 事件（INSERT-only） |
| `/outreach` | `outreach-list` | [outreach_list.py](../api/services/reports/outreach_list.py) | 查 outreach pipeline / thread |
| `/import-reply` | `import-reply` | [import_reply.py](../api/services/reports/import_reply.py) | 粘贴邮件回信 → LLM 抽 status → 自动 /log |
| `/dataroom` | `data-room` | [data_room.py](../api/services/reports/data_room.py) | 数据室文件清单（8 类 × modality × stage × audience） |
| `/synthesize` | `bd-synthesize` | [bd_synthesize.py](../api/services/reports/bd_synthesize.py) | 综合多份 task 的 markdown → BD 策略备忘 |
| `/buyers` | `buyer-matching` | [buyer_matching.py](../api/services/reports/buyer_matching.py) | 反向买方匹配：给定资产扫 MNC画像 + LLM 排 Top-N（S2-01） |

#### `/draft-X` 合同起草家族（5 个，2026-04-26 完整上线）
**结构化参数 → markdown + .docx skeleton**。所有服务共享 L0/L1 schema 验证 + gap-fill retry + 商业风险提示节 + 签署前 Checklist。每个服务在生成完毕后通过 `meta.suggested_commands` 推 `/legal contract_type=<X>` 做独立 BD-风险二次审查。

| 斜杠 alias | slug | Python 文件 | 节数 | 风险节 floor | 关键 BD 特征 |
|---|---|---|---|---|---|
| `/draft-ts` | `draft-ts` | [draft_ts.py](../api/services/reports/draft_ts.py) | 13 | ≥3 | binding/non-binding 标记 + No-Shop + Break-up Fee |
| `/draft-mta` | `draft-mta` | [draft_mta.py](../api/services/reports/draft_mta.py) | 12 | ≥3 | Material/derivative 范围 + Stealth-license 红旗扫描 |
| `/draft-license` | `draft-license` | [draft_license.py](../api/services/reports/draft_license.py) | 13 | ≥5 | Definitions ≥6 核心术语 + Diligence milestones + Effects of Termination 存续条款 |
| `/draft-codev` | `draft-codev` | [draft_codev.py](../api/services/reports/draft_codev.py) | 12 | ≥5 | 对称（Party A/B） + JSC 投票/僵局 + 成本分摊 + 共同 IP + buyout/FMV |
| `/draft-spa` | `draft-spa` | [draft_spa.py](../api/services/reports/draft_spa.py) | 13 | ≥6 | R&W 分 Fundamentals/General + Indemnification 三件套（cap+basket+survival） + HSR/CFIUS/SAMR + Working Capital Adjustment |

> ⚠️ **/draft-X 的输出都是 SKELETON**：实际合同（特别是 SPA 100+ 页 / License 50+ 页）必须由律师起草。BDGO 输出含 `Not legal advice / 非法律意见` 显著免责声明，并在 chip 中默认衔接 `/legal` 做 BD-风险二次审查。

---

## BD Lifecycle 接线图（生命周期 chips）

整套生命周期工具通过 `meta.suggested_commands` chips 串联，**前端机制通用，后端只管 emit**。下表是当前完整接线：

```
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1 — 入栈分析                                              │
│                                                                  │
│  Upload BP                                                       │
│    └→ extract metadata → "Start BD Intake"                       │
│         └→ planner mode → 7-step checklist:                      │
│              ☑ /target  ☑ /disease  ☐ /ip  ☑ /evaluate          │
│              ☑ /mnc  ☐ /timing  ☑ /synthesize ★                  │
│         └→ /synthesize task_ids=[...] → BD 策略备忘              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Stage 2 — Buyer 匹配 + outreach                                 │
│                                                                  │
│  /buyers target=X indication=Y phase=Z top_n=5  ← NEW (S2-01)  │
│    ├→ chip /mnc company_name="[排名1买方]"  (deep-dive)          │
│    └→ chip /email target=X indication=Y phase=Z                 │
│                                                                  │
│  /company perspective=buyer|seller                               │
│    ├→ chip /timing                                               │
│    │    └→ chip /email cold_outreach                             │
│    │         ├→ chip /log status=sent                            │
│    │         └→ chip /legal contract_type=cda                    │
│    ├→ chip /email                                                │
│    └→ chip /evaluate (if buyer + full asset)                     │
│                                                                  │
│  /import-reply (paste reply)                                     │
│    └→ status-driven chip:                                        │
│         · cda_signed → /dd                                       │
│         · ts_signed  → /legal contract_type=license              │
│         · meeting    → /dd prep                                  │
│         · others     → /outreach (view thread)                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Stage 3-4 — DD 准备 + Data Room                                 │
│                                                                  │
│  /dd company=X perspective=buyer    (问对方)                      │
│    ├→ chip /evaluate                                             │
│    └→ chip /rnpv                                                 │
│                                                                  │
│  /dd company=X perspective=seller   (会前 Q&A 准备)               │
│    └→ (same chips — 都是 deal evaluation)                        │
│                                                                  │
│  /dataroom asset=Y modality=adc                                  │
│    ├→ chip /dd perspective=seller                                │
│    └→ chip /legal contract_type=cda  (if licensing/partnership)  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Stage 5-6 — TS / Definitive / Acquisition                       │
│                                                                  │
│  /evaluate or /rnpv                                              │
│    └→ chip /legal contract_type=ts (review existing TS)          │
│                                                                  │
│  /draft-ts our_role=licensor financial_terms=...                 │
│    ├→ chip /legal contract_type=ts (review own draft)            │
│    └→ chip /dd perspective=seller (if licensor)                  │
│                                                                  │
│  /draft-mta provider/recipient material=...                      │
│    └→ chip /legal contract_type=mta                              │
│         + /draft-ts (if provider role)                           │
│                                                                  │
│  /draft-license licensor/licensee asset=...                      │
│    ├→ chip /legal contract_type=license                          │
│    └→ chip /dd perspective=seller (if licensor)                  │
│                                                                  │
│  /draft-codev party_a/party_b cost_split=50_50 jsc=...           │
│    └→ chip /legal contract_type=co_dev                           │
│                                                                  │
│  /draft-spa buyer/seller deal_structure=stock_purchase ...       │
│    └→ chip /legal contract_type=spa                              │
│                                                                  │
│  /legal contract_type=ts review                                  │
│    └→ chip /legal contract_type=license                          │
│         + /legal contract_type=co_dev                            │
│                                                                  │
│  /legal contract_type=mta review                                 │
│    └→ chip /legal contract_type=license                          │
└─────────────────────────────────────────────────────────────────┘
```

### 关键设计原则

1. **Chips 通用机制**：后端任何 service 都通过 `ReportResult.meta.suggested_commands: list[{label, command, slug}]` emit 下一步。前端 `ReportTaskCard` 自动渲染（不用每次改前端）。
2. **状态驱动而非硬编码**：`/log` 和 `/import-reply` 的 chips 根据 `status` 字段动态选择（cda_signed→/dd, ts_signed→/legal license, etc.），而不是固定一条链。
3. **双向服务用 perspective**：`/company`、`/dd`、`/email`、`/draft-ts`、`/draft-mta`、`/draft-license`、`/draft-codev`、`/draft-spa`、`/timing` 都接受 `perspective` / `our_role` 参数，同样的 service 服务买卖两端。
4. **Plan mode 用于多步编排**：BP 上传后 → planner 生成 N-step checklist 让用户勾选，比硬编码 orchestrator 更灵活（X-17）。

---

## 升级流程：当用户说"升级 X 技能"

1. **查映射表** —— 找到 alias 对应的 SKILL.md 路径 + Python 文件 + prompt 锚点
2. **读 SKILL.md**，重点看：
   - 顶部 frontmatter 后的"升级要点"段（如 `**v0.2.1 升级要点**（2026-04-24）：`）
   - 章节结构 / 字数 / 判定规则的最新表述
   - schema 契约和验证器引用（如有）
3. **读 Python 文件**的 prompt 锚点（见上表"Prompt 锚点"列），通常是顶层的 `SYSTEM_PROMPT` / `CHAPTER_SYSTEM_PROMPT` 字符串和章节级 `_CHX_PROMPT` 模板
4. **Diff prompt-相关内容**：
   - ✅ 同步：章节标题、章节内的写作要求、字数/视角/口径、JSON schema 字段名、判定逻辑（如"市值 > $50B 走 MNC 模式"）
   - ❌ 不动：CRM SQL 查询、Tavily web search 调用、docx_builder 渲染、ThreadPoolExecutor 并发、错误处理 —— 这些是 BDGO 工厂层、SKILL.md 里压根没有
5. **改 Python prompt 块**，保留 f-string 占位符（如 `{company}`、`{disease_display}`、`{ctx}` 等不能丢）
6. **本地试跑**：`python -m pytest api/tests/services/reports/test_<name>.py`（如有）
7. **提 PR**，title 写 `feat(<alias>): sync to SKILL.md v<X.Y.Z> (<date>)`
8. **更新本表**："本地版本/最近改动"和"prompt 锚点"行号要跟着改

### 不要做的事

- 不要把 SKILL.md 整个塞进 Python f-string —— 两边详略不同，SKILL.md 的"使用说明 / 模式判定 / 模板对照"是给人看的，进 prompt 会浪费 token
- 不要把 BDGO 的数据查询逻辑反向写回 SKILL.md —— SKILL.md 是给 MiniMax agent 用的，它的数据获取是另一套 tool calling
- 不要在没读 SKILL.md frontmatter 升级要点的情况下盲改 Python —— 会丢方向

---

## 为什么有这个文档

- BDGO Python 文件**没有**任何"我对应哪个 SKILL.md"的标记，跨 session 的 Claude 无法从代码本身推断这个映射关系
- 本地 SKILL.md 顶部有版本号（如 `v0.2.1`），但线上没有 `synced_from_version` 字段
- 这两点叠加导致"升级 X 技能"是个**项目 specific 的术语**，不读这份文档就不知道是什么意思

每个 mirrored Python 文件顶部都有 `# MIRROR OF: ~/.openclaw/skills/<name>/SKILL.md (...)` 注释头（X-58, 2026-04-26），让代码本身自描述。改 prompt 前先读 header 指向的 SKILL.md，避免本地/线上漂移。

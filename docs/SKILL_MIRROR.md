# Skill Mirror — BDGO 报告服务 vs 本地 OpenClaw 技能

BDGO 的 11 个 ReportService 中有 **8 个**是本地 OpenClaw 技能的**线上 Python 实现**。本地 SKILL.md 是 prompt 的"原稿"，迭代快；BDGO Python 文件是"工厂"，把 prompt 嵌入完整的报告生产流水线（CRM 查询 → web 增强 → LLM → docx 渲染）。

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

## 镜像映射表（8 对）

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

### 线上独有（无本地镜像）

这 3 个 ReportService **没有**对应的 SKILL.md，prompt 直接长在 BDGO 里：
- [paper_analysis.py](../api/services/reports/paper_analysis.py)（`/paper`）
- [target_radar.py](../api/services/reports/target_radar.py)（`/target`）
- [clinical_guidelines.py](../api/services/reports/clinical_guidelines.py)（`/guidelines`）

如果要给这 3 个建立镜像，先在 `~/.openclaw/skills/` 下建 `SKILL.md`、把现有 Python prompt 拆出去、然后把这一行加进上表。

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

下一步可以加每个 Python 文件顶部的 `# MIRROR OF: ... synced from v0.2.1` 注释头，让代码本身自描述（详见 README todo）。

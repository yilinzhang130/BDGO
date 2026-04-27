# BD GO — 战略 Roadmap（2026-04-27 起）

> 这份文档是**长期产品演进路线图**，与战术性的 `TODO.md` 互补。
> 总目标：从"30 个 slash 平铺的 chat 工具集" → "三个 workspace + 轻量 chat 的产品形态"。
> 完成后产品架构与心智模型对齐 BD 真实工作流：**我要卖 / 我要买 / 项目管理 + 分析助手**。
>
> **如何使用**：把任何 phase ID 发给我（如 "Phase 2 进度" 或 "P5-3 状态"），我都能定位并继续。

---

## 0. 当前基线（2026-04-27）

### 已完成（强基础）
- 30 个 ReportService + 8 个 chat tools 全部上线
- L0/L1 质量验证覆盖 9 个核心服务（/paper 待补）
- Plan mode + Plan 模板系统（5 内置 + 用户保存）
- BD 生命周期 chip 编排（teaser → NDA → DD → TS → drafts → legal）
- 团队功能（共享 watchlist + 通知铃 + 报告通知）
- Stripe 订阅 + credits 系统
- PWA + 移动端响应式
- 中英 UI 切换
- 用户文档（28 命令完整列表）+ docs 渲染修复

### 未解决的产品级问题（这份 Roadmap 要回答）
1. **Chat 太重**：30 个 slash 既混着分析工具，又混着流程节点，新用户 onboarding 困难
2. **流程感缺失**：BD 真实场景是"我要卖某资产" / "我要买某领域"，但产品不显式建模这个意图
3. **状态散落**：每个 chat 是孤岛，同一资产/deal 跨多个 chat 的上下文丢失
4. **质量与可观测性弱**：成本、延迟、成功率没有仪表盘，质量漂移无觉察
5. **数据未结构化**：contacts / conferences / deal_terms 都是硬编码或自由文本

---

## 1. 总体架构目标（North Star）

```
BD GO（重构后）
├─ 💬 Chat（轻）  ─────────  无状态分析问答 + ~10 个 A 类 slash
├─ 🎯 Sell-side workspace  ─  "我要卖" 完整流程
├─ 🔍 Buy-side workspace  ──  "我要买" 完整流程
└─ 📊 Project workspace  ───  跨 session 状态聚合
```

**Chat 的新定位**：BD 分析师的"思考伙伴"，不是流程引擎。
- 入口：从 workspace 点"问 AI"，自动带资产/项目上下文
- 出口：chat 结论可"采纳到 workspace"，写回 CRM
- 保留 slash：仅 A 类纯查询型（10 个左右）

---

## 2. Slash 三类分级（Phase 1 的判断依据）

### A 类（10 个）— 保留 chat slash
单输入 → 单报告 → 读完即走，无后续状态。
- `/paper` `/mnc` `/company` `/disease` `/target` `/ip` `/guidelines` `/rnpv` `/commercial` `/evaluate`

### B 类（11 个）— 退役 slash，搬入 workspace 表单
有结构化输入或上下游依赖，prompt 拼接困难。
- `/buyers` `/teaser` `/dataroom` `/dd` `/faq` `/meeting` `/timing`
- `/draft-ts` `/draft-mta` `/draft-license` `/draft-codev` `/draft-spa`

### C 类（5 个）— 彻底从 slash 移除
写状态 / 列表浏览，根本不该是 query。
- `/log` `/outreach` `/import-reply` `/batch-email` `/email`

---

## 3. 阶段路线图

### Phase 1 — Slash 审计 + Outreach Workspace 探针（2 周，低风险）

**目标**：用最小改动验证"workspace 化"假设；C 类 slash 从 popup 消失。

| ID | 任务 | 工 |
|---|---|---|
| P1-1 | Slash 类别打标（A/B/C 元数据写入 SLASH_COMMANDS） | S |
| P1-2 | C 类（5 个）从 popup 隐藏，但 backend 保留兼容 | S |
| P1-3 | 新建 `/outreach` 独立页（pipeline 列表 + 状态 filter + 搜索） | M |
| P1-4 | Compose 邮件：表单化 `/email`（收件人 + 资产卡 + 语调 + 语言） | M |
| P1-5 | 粘贴回信：modal 形式 `/import-reply`（粘贴框 + 解析预览 + 确认归档） | S |
| P1-6 | 批量外联：`/batch-email` 多收件人选择器 | M |
| P1-7 | Chat 内"打开 outreach 页"快捷链接（替代 chat 里的 list 输出） | S |
| P1-8 | 量化指标：埋点 outreach 完成率、回信归档率 | S |

**成功标准**：
- Chat slash popup 项数 30→25
- Outreach 完成率（/email → /log → /import-reply 闭环率）较基线 +30%
- 用户调研：5 个用户中至少 3 个说"outreach 页比 chat 里输 / 简单"

**回退方案**：Workspace 不顺手就保留兼容路径，slash 重新加回 popup。

---

### Phase 2 — Sell-side Workspace（4 周，主体重构）

**目标**："我要卖"成为产品一级入口，把 11 个 B 类 slash 中卖方相关的全部纳入。

| ID | 任务 | 工 |
|---|---|---|
| P2-1 | `/sell` 顶部导航入口 + 卖方资产列表页 | M |
| P2-2 | 资产 detail 页升级（替换现有 chat-only 入口） | M |
| P2-3 | "Match buyers" 按钮（替代 `/buyers`，结果落在资产页） | M |
| P2-4 | "Generate teaser" 按钮 + 按买方定制变体（解决 S2-02） | M |
| P2-5 | DD 准备子页（合并 `/dd seller` + `/faq` + `/meeting` 为时间线） | L |
| P2-6 | Data room 子页（`/dataroom` 输出 → 可勾选 checklist + 上传文件占位） | L |
| P2-7 | Drafts 子页（5 个 `/draft-*` 通过 form 触发，参数表单） | L |
| P2-8 | "采纳到 workspace"：chat 里讨论的结论一键写入资产页 | M |
| P2-9 | 资产 → outreach pipeline 关联（点资产看相关历次外联） | S |

**成功标准**：
- 一个新用户能在 30 分钟内完成"上传 BP → match buyers → 生成 teaser → 起草 TS"完整闭环
- B 类卖方 slash（/buyers /teaser /dd /faq /meeting /dataroom /draft-*）从 popup 隐藏
- 卖方流程平均 deal lead time（从 BP 上传到 TS 生成）较 chat-only 缩短 ≥40%

---

### Phase 3 — Buy-side Workspace + Project（4 周）

**目标**："我要买"workspace 上线 + Project 概念落地（解决 X-20 / X-21）。

| ID | 任务 | 工 |
|---|---|---|
| P3-1 | `/buy` 顶部导航 + watchlist 升级为常驻 buy-side 主页 | M |
| P3-2 | Scout 模块：把 `/disease` `/target` `/ip` 升级为可订阅追踪 | M |
| P3-3 | 评估流：watchlist 资产 → `/evaluate` `/rnpv` `/commercial` 一键链 | M |
| P3-4 | Buy-side DD 子页（`/dd buyer` + `/faq` 视角切换） | M |
| P3-5 | `/legal review` 升级为合同审查 workspace（多份合同 vs 多份模板） | M |
| P3-6 | Project 实体：用户可创建 project，绑定资产 + chat + 报告 + outreach | L |
| P3-7 | 跨 session 上下文：进 project 后所有 chat 自动带 project context | M |
| P3-8 | Project timeline 视图（按时间排所有事件 / 报告 / 邮件） | M |

**成功标准**：
- 买方用户能从 watchlist 出发，无需 chat 完成完整 DD 评估
- 一个 project 能聚合 ≥3 chats + ≥5 reports + ≥10 outreach 记录
- 老用户回访率（30 天 retention）+15%

---

### Phase 4 — Chat 重定位（1 周，可与 Phase 3 并行）

**目标**：Chat 变"分析助手"，slash popup 仅剩 A 类。

| ID | 任务 | 工 |
|---|---|---|
| P4-1 | Slash popup 默认仅显示 A 类（10 个），B/C 类需 deep link 触发 | S |
| P4-2 | Chat 启动时若来自 workspace，顶部显示"working on: [资产 / 项目]"上下文条 | S |
| P4-3 | "采纳到 workspace"按钮（chat message → 写入 project notes / 资产备注） | M |
| P4-4 | 空 chat 状态升级：根据用户是否有 active project 推荐入口 | S |
| P4-5 | 命令分类总览升级：popup 顶部加"📊 分析""📦 流程在 workspace"分组 | S |

**成功标准**：
- 新用户在 chat 里看到 popup 只有 10 项，无认知过载
- workspace 用户的 chat 平均 token 消耗降低（短对话占比上升）

---

### Phase 5 — 质量、可观测性、退款（3 周，可与 Phase 2/3 并行）

**目标**：补齐 P1 级 cross-cutting gap，让产品"内功"配得上前端重构。

| ID | 对应 Gap | 任务 | 工 |
|---|---|---|---|
| P5-1 | X-45/46/47 | Per-service dashboard：成功率 / P50 P99 / token 消耗 | M |
| P5-2 | X-77 | LLM 失败自动退 credits + 用户可见的 transaction history | S |
| P5-3 | X-52 | Fixture-based eval harness（本地跑固定 BP，diff 输出） | M |
| P5-4 | X-06 | 黄金样本回归测试：CI 跑 N 个 fixture，输出差异 >X% 报警 | L |
| P5-5 | S1-08 / X-05 | /paper L0/L1 schema 补完（最后一个未覆盖服务） | M |
| P5-6 | X-64 | LLM 月度成本警报（超阈值发邮件） | S |
| P5-7 | X-66 | Per-service rate limit（防 /evaluate 被狂刷） | M |
| P5-8 | X-67 | （已完成）确认 PR #115 真的修了 flake | — |
| P5-9 | X-49/50 | 用户 retention / engagement / 最常用 service 排行 | M |

**成功标准**：
- 任何服务的 P99 延迟 / 失败率可在 admin 页一眼看到
- 用户失败的 LLM 调用 100% 自动退 credits
- 修改任何 prompt 后能跑 fixture diff，量化"变好/变坏"

---

### Phase 6 — 数据资产化（4 周）

**目标**：把硬编码 / 自由文本数据升级为结构化表，为后续 BI 与协作铺路。

| ID | 对应 Gap | 任务 | 工 |
|---|---|---|---|
| P6-1 | X-08 / S2-14 | contacts 表：人 → 多公司、多 thread | M |
| P6-2 | X-09 | conferences 表 live 化（替代硬编码 8 个） + admin 维护 UI | M |
| P6-3 | X-10 / S5-03 | deal_terms 可比库：公开 TS 数据入库 + `/draft-ts` 锚点引用 | L |
| P6-4 | X-11 / S1-12 | portfolio 表：用户公司全管线 vs 市场 | M |
| P6-5 | X-13 | CRM 数据新鲜度指标（每条记录最后更新时间） | S |
| P6-6 | X-15 | CRM 改动审计日志 | M |
| P6-7 | X-16 | CRM chat 写入路径（在 chat 里说"更新 Pfizer 这条" → 自动 commit） | M |
| P6-8 | S5-04 | TS 情景分析（upfront 改了 → rNPV 自动重算） | M |

**成功标准**：
- /timing 不再依赖硬编码会议
- /draft-ts 起草时自动引用 ≥3 条可比交易
- 团队成员能查到"上周 Alice 改了哪些 CRM 记录"

---

### Phase 7 — 集成 / 外部数据 / 协作（5 周）

**目标**：从孤岛 SaaS 升级为"嵌入 BD 工作流"的工具。

| ID | 对应 Gap | 任务 | 工 |
|---|---|---|---|
| P7-1 | X-32 | 任务完成邮件通知（长任务 LLM 调用完发邮件） | S |
| P7-2 | S2-05 / X-28 | 邮件转发架构：自定域名 + 入站 webhook + 自动归档 | L |
| P7-3 | X-34 | PubMed 直连 API | M |
| P7-4 | X-35 | USPTO/EPO 专利搜索（升级 /ip 数据精度） | L |
| P7-5 | X-37 | Press release / IR feed RSS 订阅器 | M |
| P7-6 | X-29 | Slack/Teams 通知出站 | M |
| P7-7 | X-40/41 | 报告 comment thread + @mentions | M |
| P7-8 | X-42 | 权限分级：analyst / partner / admin tier | M |
| P7-9 | X-43 | 用户行为审计日志 | M |

**成功标准**：
- 用户买家通过转发邮件即可让 BD GO 自动归档
- /ip 输出包含真实专利号引用
- 团队 admin 可分配只读 / 编辑权限

---

### Phase 8 — 商业化深化（2 周）

**目标**：让付费心智更清晰，降低试用门槛。

| ID | 对应 Gap | 任务 | 工 |
|---|---|---|---|
| P8-1 | X-75 | Trial 模式：注册即送 N credits，14 天 | M |
| P8-2 | X-73 | Per-service 定价（/draft-license 比 /paper 贵） | S |
| P8-3 | X-76 | 用量预测仪表盘（按当前用法本月会花多少） | S |
| P8-4 | X-74 | （已完成 PR #149）确认 subscription tier 真的能切换 | — |

**成功标准**：
- 注册 → 完成首次报告的转化率 +50%
- 月活付费用户 / 月活总用户 ≥ 15%

---

## 4. Backlog（P3 / P2 长尾，按需排期）

未进入主路线，但记录在案，避免遗忘：

- **文档增强**：X-23 Word track-changes / X-24 PDF / X-25 PPT 模板库 / X-27 图表生成
- **协作深化**：X-44 多人协同写作 / X-79 报告全文搜索 / X-80 chat 历史搜索
- **外部数据高端**：X-38 Bloomberg/FactSet（贵，等付费用户要求再做）
- **国际化**：X-69 所有服务 language 参数 / X-70 外文 BP 翻译
- **可访问性**：X-72 a11y 审计
- **UX 细节**：X-78 报表卡片折叠 / X-82 键盘快捷键 / X-83 多 chat 并行 view
- **运维**：X-62 staging 确认 / X-63 部署 smoke test / X-65 DB 备份可见性
- **dev 工具**：X-51 prompt 版本管理 / X-53 LLM 确定性 mode / X-54 prompt registry
- **大架构**：X-19 后台 watcher / X-22 用户层 cron / X-31 native mobile app
- **数据**：X-12 competitor_intel 表 / X-14 CRM 自动 enrichment

---

## 5. 排期总览

| Phase | 内容 | 工程量 | 可并行？ |
|---|---|---|---|
| Phase 1 | Slash 审计 + Outreach 探针 | 2 周 | — |
| Phase 2 | Sell-side workspace | 4 周 | 与 P5 并行 |
| Phase 3 | Buy-side workspace + Project | 4 周 | 与 P5 并行 |
| Phase 4 | Chat 重定位 | 1 周 | 与 P3 并行 |
| Phase 5 | 质量 / 可观测 / 退款 | 3 周 | 与 P2/P3 并行 |
| Phase 6 | 数据资产化 | 4 周 | — |
| Phase 7 | 集成 / 外部数据 / 协作 | 5 周 | — |
| Phase 8 | 商业化深化 | 2 周 | — |

**串行总计**：25 周（≈6 个月）
**最大并行**：16-18 周（≈4 个月）

---

## 6. 决策检查点（Go/No-Go gate）

| 时点 | 决策 | 依据 |
|---|---|---|
| Phase 1 完成后 | Workspace 化是否成立？ | Outreach 完成率 / 用户访谈 |
| Phase 2 完成后 | 卖方流程是否真的快了？ | Lead time 数据 + retention |
| Phase 3 完成后 | Project 概念是否被使用？ | Project 创建率 / 单 project 平均 chat 数 |
| Phase 5 完成后 | 质量基线是否建立？ | 黄金样本 diff CI 是否绿 |
| 每月 | 调整后续 phase 顺序 | 用户反馈 + 商业指标 |

---

## 7. 风险登记

| 风险 | 缓解 |
|---|---|
| Workspace 化用户教育成本高 | Phase 1 探针 + 每个 phase 保留 slash 兼容兜底 |
| MiniMax 配额硬天花板（已知） | Phase 5 加成本仪表盘提前预警；Phase 1-7 部分 prompt 可换 Claude/DeepSeek |
| 团队功能（X-42 权限分级）改动深 | Phase 7 统一改，期间不动 schema |
| 重构期间老用户体验下降 | A 类 slash 全程保留；C 类移除前 2 周加 banner 提示 |

---

## 8. 与 AIDD 的关系

AIDD = asset discovery（资产发现，0→1）
BD GO = deal lifecycle（交易生命周期，0→签约）

**未来融合点**：
- AIDD 选定资产 → 一键导入 BD GO 的 "我要卖" workspace
- BD GO 买方 watchlist → 反向调 AIDD 的资产库做扩展搜索

不在本 Roadmap 范围内，但 Phase 3 的 Buy-side workspace 设计应预留接口。

---

**文档版本**：v1.0（2026-04-27）
**下次更新**：Phase 1 完成时（约 2026-05-11）

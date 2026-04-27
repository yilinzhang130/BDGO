// 使用文档正文与目录。更新后 Vercel 会自动重新部署。

export const DOCS_VERSION = "v1.0";
export const DOCS_UPDATED = "2026-04-22";

export type TocItem = { id: string; title: string; level: 2 | 3 };

export const DOCS_TOC: TocItem[] = [
  { id: "quickstart", title: "快速开始", level: 2 },
  { id: "account", title: "注册与登录", level: 3 },
  { id: "first-query", title: "第一次对话", level: 3 },
  { id: "chat", title: "对话与 Agent", level: 2 },
  { id: "plan-mode", title: "Plan Mode", level: 3 },
  { id: "search-mode", title: "Search Mode", level: 3 },
  { id: "context-panel", title: "上下文面板", level: 3 },
  { id: "sessions", title: "会话管理", level: 3 },
  { id: "reports", title: "Slash 报告命令", level: 2 },
  { id: "report-categories", title: "命令分类总览", level: 3 },
  { id: "mnc-report", title: "/mnc 买方画像", level: 3 },
  { id: "evaluate-report", title: "/evaluate 资产评估", level: 3 },
  { id: "rnpv-report", title: "/rnpv 估值模型", level: 3 },
  { id: "other-reports", title: "完整命令清单", level: 3 },
  { id: "data", title: "结构化数据浏览", level: 2 },
  { id: "catalysts", title: "催化剂日历", level: 3 },
  { id: "conferences", title: "会议洞察", level: 3 },
  { id: "watchlist", title: "关注列表", level: 3 },
  { id: "collab", title: "协作与导出", level: 2 },
  { id: "upload", title: "文件上传", level: 3 },
  { id: "share", title: "分享链接", level: 3 },
  { id: "export", title: "Word / PDF 导出", level: 3 },
  { id: "account-settings", title: "账户与 API", level: 2 },
  { id: "preferences", title: "个性化偏好", level: 3 },
  { id: "api-keys", title: "API Keys", level: 3 },
  { id: "faq", title: "常见问题", level: 2 },
];

export const DOCS_BODY = `
## <a id="quickstart"></a>快速开始

BD Go 是面向 BD 与立项场景的多 Agent 协作平台。下面三步让您从注册到拿到第一份报告。

### <a id="account"></a>注册与登录

1. 访问 [bdgo.ai](https://bdgo.ai) 点击右上角 **登录**。
2. 使用邮箱注册；已有账号直接登录。
3. 首次登录会引导您填写角色、关注领域等基本信息——这些会用于后续 AI 回答的个性化。

### <a id="first-query"></a>第一次对话

登录后直接进入 **对话页**。推荐从以下方式之一开始：

- **描述一句话需求**：比如 "帮我分析一下 Moderna 2025 年以来的 BD 策略"。
- **使用 slash 命令**：输入框里键入 \`/\`，会弹出 11 个即用报告的命令面板（见下文）。
- **从数据浏览入口切入**：在左侧导航打开 *公司 / 资产 / 临床 / 交易* 等视图，看到感兴趣的条目点击 → AI 对话面板会自动带上下文。

Agent 回答时会引用来源（文献、公开数据库、交易记录），可点击展开验证。

---

## <a id="chat"></a>对话与 Agent

对话是 BD Go 的主入口。平台不是单一 LLM，而是由**多个专精 Agent** 协同工作：资产发现 Agent、买方画像 Agent、估值 Agent、文献 Agent 等。对话引擎会根据意图自动调度。

### <a id="plan-mode"></a>Plan Mode

复杂任务（比如"做一份 X 公司的完整买方画像"）下，开启 Plan Mode 可以让 Agent 先输出拆解计划供您确认，再正式执行。

| 模式 | 行为 |
|---|---|
| **Auto**（默认） | Agent 判断任务复杂度，只对需要拆解的任务先展示计划 |
| **On** | 任何任务都先出计划，防止跑偏 |
| **Off** | 跳过计划直接执行——适合简单查询与快速迭代 |

在输入框左下角切换。

### <a id="search-mode"></a>Search Mode

| 模式 | 用途 |
|---|---|
| **Agent**（默认） | 深度研究——调用内部数据 + 文献 + 交易库做结构化回答 |
| **Quick** | 事实性快查——直接跳转 Web 搜索，适合"X 公司今天股价"这类问题 |

### <a id="context-panel"></a>上下文面板

侧边栏的 **Context** 区可以把当前关注的公司 / 资产固定住，跨多轮对话持续使用。例：先搜索 Moderna 把它加进 Context，接下来所有问题都会自动围绕它展开。

### <a id="sessions"></a>会话管理

- 每段对话自动保存为一个 session，左栏 **Chat History** 可查看、重命名、删除、分组。
- 任何历史会话都可以继续追问——上下文不丢失。
- 会话支持导出为 Word / PDF，便于归档或传阅。

---

## <a id="reports"></a>Slash 报告命令

对话输入框里键入 \`/\` 唤出命令面板，按 ↑↓ 选择、Enter 触发。这些是把最高频 BD 场景固化成的"一键模板"，目前共 28 个，每个都调用专门的 Agent 链路。

### <a id="report-categories"></a>命令分类总览

| 类别 | 命令 |
|---|---|
| **买方与匹配** | \`/mnc\` \`/buyers\` \`/company\` |
| **资产评估** | \`/evaluate\` \`/rnpv\` \`/dd\` \`/faq\` |
| **市场与竞争** | \`/disease\` \`/target\` \`/commercial\` \`/ip\` \`/guidelines\` |
| **文献分析** | \`/paper\` |
| **对外材料** | \`/teaser\` \`/dataroom\` \`/meeting\` |
| **外联与执行** | \`/email\` \`/batch-email\` \`/outreach\` \`/log\` \`/import-reply\` \`/timing\` |
| **合同起草** | \`/draft-ts\` \`/draft-license\` \`/draft-codev\` \`/draft-mta\` \`/draft-spa\` \`/legal\` |
| **战略综合** | \`/synthesize\` |

### <a id="mnc-report"></a>/mnc 买方画像

输入 \`/mnc 辉瑞\` 或 \`/mnc Pfizer\`，30~60 秒后得到一份结构化报告：

1. **管线全景**：按治疗领域拆分，标注竞争对手对标与潜在缺口
2. **历史 BD 图谱**：近 5 年 License / M&A / Collab 的时间轴
3. **高管战略信号**：公开 earnings call / 访谈里提到的重点
4. **财务买方能力**：现金流 + 债务 + BD 预算估算
5. **中国 BD 机会矩阵**：按加权评分推荐匹配标的

支持 MNC 英文名与中文名。

### <a id="evaluate-report"></a>/evaluate 资产评估

输入资产名或 NCT 号，系统从四个维度打分（生物学合理性、临床数据质量、商业前景、交易可行性），并输出：

- 创新层级判断（Fast Follower / Me-Too / Best-in-Class / First-in-Class）
- 核心风险与卖点
- 对典型买方的吸引力预估

### <a id="rnpv-report"></a>/rnpv 估值模型

基于临床阶段、适应症、市场规模、同类资产交易倍数等参数，产出 **可直接下载的 Excel**（Base / Bull / Bear 三场景），关键假设可手工覆盖重算。

### <a id="other-reports"></a>完整命令清单

| 命令 | 产物 |
|---|---|
| \`/mnc\` | MNC 买方画像 |
| \`/buyers\` | 反向买方匹配（Top-N） |
| \`/company\` | 公司深度分析 |
| \`/evaluate\` | 资产交易吸引力评估 |
| \`/rnpv\` | rNPV 估值模型（Excel） |
| \`/dd\` | DD 问题清单 |
| \`/faq\` | DD FAQ 速答稿 |
| \`/disease\` | 疾病竞争格局 |
| \`/target\` | 靶点雷达 |
| \`/commercial\` | 商业化机会评估 |
| \`/ip\` | IP 专利格局 |
| \`/guidelines\` | 临床指南摘要 |
| \`/paper\` | 文献分析 / 综述 |
| \`/teaser\` | 资产 Teaser（PPT + Word） |
| \`/dataroom\` | Data Room 清单 |
| \`/meeting\` | 会前简报 |
| \`/email\` | 外联邮件初稿 |
| \`/batch-email\` | 批量外联邮件 |
| \`/outreach\` | 外联管线追踪 |
| \`/log\` | 外联记录日志 |
| \`/import-reply\` | 邮件回复自动归档 |
| \`/timing\` | 外联时机建议 |
| \`/draft-ts\` | Term Sheet 起草 |
| \`/draft-license\` | License 协议起草 |
| \`/draft-codev\` | Co-Development 协议起草 |
| \`/draft-mta\` | MTA 起草 |
| \`/draft-spa\` | SPA / M&A 协议起草 |
| \`/legal\` | 合同法律风险审查 |
| \`/synthesize\` | 多报告 BD 策略综合 |

所有报告都是 **可追溯、可引用、可导出**——每个结论都带来源链接。完整参数与示例直接在对话里键入命令查看即时提示。

> **提示**：复杂资产评估和外联场景会涉及多个命令，例如先 \`/mnc\` 选目标买方，再 \`/email\` 起草初稿，最后 \`/log\` 记录沟通。

---

## <a id="data"></a>结构化数据浏览

除对话外，顶部导航提供六大结构化库：

- **公司**：biotech / MNC / CRO / VC 等全球主体
- **资产**：分子、细胞治疗、基因治疗、器械、平台
- **临床**：ClinicalTrials.gov 镜像 + 结构化治疗方案
- **交易**：License / M&A / Collaboration 历史
- **买方**：MNC 买方画像库
- **专利 / IP**：核心专利族与到期跟踪

每个视图支持关键词搜索、按国家 / 阶段 / 适应症 / 金额过滤、导出 CSV。

### <a id="catalysts"></a>催化剂日历

**催化剂日历**是一个独立视图，按时间聚合所有临床读出、监管决策、公司里程碑节点：

- **列表视图**：按紧迫度（逾期 / 临近 / 近期 / 远期）自动着色
- **12 个月网格**：一眼看全年关键事件分布
- 支持按公司 / 适应症 / 阶段过滤，订阅追踪列表

### <a id="conferences"></a>会议洞察

针对 **AACR / ASCO / ASH** 等主流会议，BD Go 做了 abstract / poster / late-breaking 的聚合 + BD 热度标注：

- 所有摘要按 **治疗领域、靶点、公司** 多维索引
- 每条摘要附 **AI 解读**（临床意义、竞争影响、BD 提示）
- 侧边栏可直接调起 AI 对话，基于该会议上下文深入追问

### <a id="watchlist"></a>关注列表

在任何公司、资产、疾病、靶点或孵化器详情页点击 ⭐ 添加到关注列表。关注的条目会：

- 汇总到个人 **Watchlist** 页面，支持筛选排序
- 有新 BD 动态 / 临床读出时触发通知（开发中）
- 与 AI 对话联动——可以直接说 "分析我关注的这几家公司的 BD 匹配度"

---

## <a id="collab"></a>协作与导出

### <a id="upload"></a>文件上传

对话输入框支持 **上传 PDF / PPTX / DOCX**。上传后该文件会进入当前会话的上下文，AI 回答时会引用文件里的具体内容。典型用法：

- 把一份 BP / Teaser / 年报上传 → 追问 "这家公司的核心资产临床进展如何？"
- 把一批 abstract 上传 → 让 AI 做交叉汇总

### <a id="share"></a>分享链接

任何 AI 生成的报告页都有 **分享** 按钮。生成后的链接：

- **只读**，收件方无需账户
- 链接内容永久可见（除非您主动吊销）
- 可用于对外推介、内部评审、跨团队协作

### <a id="export"></a>Word / PDF 导出

报告页右上角 **导出** 菜单支持：

- **Word (.docx)**：保留标题层级、表格、引用——可直接给投委会使用
- **PDF**：固定排版，适合邮件附件
- **Excel (.xlsx)**：仅 \`/rnpv\` 估值报告

---

## <a id="account-settings"></a>账户与 API

### <a id="preferences"></a>个性化偏好

**个人设置 → 偏好** 页支持：

- 填写角色 / 关注领域 / 工作背景——AI 在生成报告时会结合这些信息调整语气和深度
- 切换数据库导航（高级用户可开启更多结构化视图）
- 切换报告卡片 / 对话模板的默认展现

### <a id="api-keys"></a>API Keys

**个人设置 → API Keys** 支持自助创建、查看、吊销 API Key，用于程序化访问：

- Key 格式：\`bdgo_live_<32位 base62>\`（共 42 字符，约 190 位熵）
- 完整 key 仅在创建时显示一次，之后只保留前 8 字符前缀用于识别
- 每个账户最多 10 个 active key
- 每个 key 可单独设置每日配额
- 吊销立即生效，请求日志全留痕

API 端点与调用示例见 [API 文档](/api-docs)。

---

## <a id="faq"></a>常见问题

**Q：BD Go 和普通大模型对话有什么区别？**

A：普通 LLM 没有实时的临床库 / 交易库 / 文献库上下文，也不会按 BD 场景做任务拆解。BD Go 的每次回答都会 **从结构化数据 + 最新文献里取证**，并按 BD 专家的工作流（四象限评估、rNPV、买方画像等）组织。

**Q：数据多久更新一次？**

A：临床数据库每日镜像；交易库每周更新；会议 abstract 在会议开幕后 24h 内完整入库；文献每日增量。

**Q：支持哪些语言？**

A：中英双语，任意一种输入均可。报告默认按输入语言输出，也可显式指定。

**Q：数据会被用于模型训练吗？**

A：不会。对话记录仅用于回溯与个人使用，我们**不用客户数据训练任何模型**。详情见 [隐私政策](/privacy)。

**Q：遇到问题或想要建议反馈？**

A：邮箱 [product@bdgo.ai](mailto:product@bdgo.ai)，通常 1 个工作日内回复。重大 bug 请在邮件标题加 [BUG]。

---

*本文档持续更新。欢迎在使用过程中告诉我们哪里讲得不够清楚。*
`;

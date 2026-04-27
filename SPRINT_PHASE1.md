# Sprint: Phase 1 — Slash 审计 + Outreach Workspace 探针

**目标**：2 周内验证"workspace 化"假设 + C 类 slash 从 popup 消失。
**对应 ROADMAP**：Phase 1（P1-1 到 P1-8）
**起始日期**：2026-04-28
**目标完成**：2026-05-11

---

## 当前状态盘点

- ✅ Outreach 数据后端：`OutreachListService` 已存在，输出 `meta.outreach_pipeline_rows`
- ✅ Chat 内嵌组件：`OutreachMiniTable.tsx` 已实装
- ❌ 独立 `/outreach` 页面：**不存在**
- ❌ 直连 API endpoint：现在只能通过跑 `/outreach` slash 间接获取
- ❌ Slash 类别元数据（A/B/C 标签）

---

## PR 拆分（10 个 PR，每个 ≤ 500 行）

### PR 1 — Slash 类别元数据基础 [P1-1]
**目的**：给每个 slash 加 `category: "A" | "B" | "C"` 标签，为后续过滤铺路。

**改动**：
- `frontend/src/components/ui/SlashCommandPopup.tsx`：`SLASH_COMMANDS` 数组每条加 `category` 字段
- 新增 `SLASH_CATEGORY_LABELS`：`{ A: "分析", B: "流程（即将迁出）", C: "已迁出" }`
- 不改 popup 渲染，纯数据准备

**测试**：
- vitest unit 测每条命令都有 category
- 类别分布断言：A=10, B=11, C=5

**估时**：0.5 天 · **大小**：~80 行

---

### PR 2 — 直连 Outreach API endpoints [P1-3 后端]
**目的**：把 outreach 数据从 "跑 slash 才有" 改成 RESTful，前端可直接拉。

**改动**：
- 新建 `api/routers/outreach.py`（参考 `watchlist.py` 结构）：
  - `GET /api/outreach/pipeline?status=&search=&page=` — 列表 + 过滤 + 分页
  - `GET /api/outreach/{id}` — 单条详情
  - `GET /api/outreach/threads?contact=` — 同一人的历史
  - `POST /api/outreach/log` — 手工补录（替代 `/log` slash 的 backend）
  - `DELETE /api/outreach/{id}` — 删除
- 复用 `OutreachListService` 内部的查询逻辑（抽到 `services/outreach_repo.py`）
- pytest：8-10 条 endpoint 测试

**测试**：
- 单元测 + 集成测（带 auth）
- 确认 `/outreach` slash 仍可用（向下兼容）

**估时**：1.5 天 · **大小**：~400 行

---

### PR 3 — `/outreach` 独立页面（pipeline 视图）[P1-3 前端]
**目的**：用户能在 chat 之外管理 outreach pipeline。

**改动**：
- 新建 `frontend/src/app/outreach/page.tsx`
- 顶部 nav 加入口（与 `/watchlist` 并列）
- 字段列：Date · Counterparty · Asset · Stage badge · Last update · Actions
- 状态 filter（draft / sent / replied / signed / dropped）
- 关键词搜索（counterparty / asset 模糊匹配）
- 分页 / 无限滚动
- 行点击 → 展开详情 panel（thread events）

**测试**：
- vitest：基础渲染 + filter 切换
- 手动跑通：登录 → 看到 pipeline → filter → 点行展开

**估时**：2 天 · **大小**：~450 行

---

### PR 4 — Compose Email 表单页 [P1-4]
**目的**：替代 chat 里输 `/email`，用结构化表单提升完成率。

**改动**：
- 新建 `frontend/src/app/outreach/compose/page.tsx`
- 表单字段：
  - 收件人（contact picker，下拉历史 + 手动）
  - 公司（自动填，可改）
  - 关联资产（从 watchlist / 已上传 BP 选）
  - 语调（initial / follow-up / nudge）
  - 语言（en / zh）
  - 自由 prompt 框（可选补充）
- "预览" → 调 `/api/reports/run/outreach-email`，渲染 markdown 到右栏
- "确认发送（自动 log）" → 写 outreach_log
- chat compose 入口：outreach 页右上角 "+ New email" 按钮

**测试**：
- 手动跑通：选资产 → 选对手 → 预览 → 确认 → 在 pipeline 看到新行
- vitest：表单校验（必填）

**估时**：2 天 · **大小**：~500 行

---

### PR 5 — Paste-Reply Modal [P1-5]
**目的**：粘贴回信 → 解析 → 归档，从 chat slash 升级为 modal。

**改动**：
- 新建 `frontend/src/components/outreach/ImportReplyModal.tsx`
- 触发入口：outreach 页 thread 详情面板里 "+ 导入对方回信" 按钮
- Modal 内容：
  - 大文本框（粘贴邮件正文）
  - 自动调 `/api/reports/run/import-reply` 解析
  - 解析结果预览：detected status / next-step / 关键词
  - 用户可改字段后点"归档"
- 归档后自动刷新 thread 视图

**测试**：
- 手动跑通：粘贴一封回信 → 看到解析 → 归档 → thread 多一条
- 解析失败 fallback 到手工填写

**估时**：1.5 天 · **大小**：~350 行

---

### PR 6 — Batch Email Compose [P1-6]
**目的**：一次给 5 家 MNC 发邮件，替代 chat 里输 `/batch-email`。

**改动**：
- 在 `outreach/compose/page.tsx` 加 "批量模式" toggle
- 收件人变多选（公司列表 + 联系人 picker）
- 公共参数：资产 / 语调 / 语言
- 每收件人可单独看预览（tab 切换）
- 一键全部发送 → N 条 outreach_log

**测试**：
- 手动跑通：选 3 公司 → 预览 3 份 → 发送 → pipeline 多 3 行
- 单家失败不影响其他

**估时**：1.5 天 · **大小**：~300 行

---

### PR 7 — C 类 Slash 隐藏 + Banner 提示 [P1-2]
**目的**：5 个 C 类 slash 从 popup 消失，但 backend 兼容。

**改动**：
- `SlashCommandPopup.tsx`：默认 filter `category !== "C"`
- C 类（`/log` `/outreach` `/import-reply` `/batch-email` `/email`）依然能输入触发，但 popup 不展示
- 用户输 C 类 slash 时，输入框上方弹"💡 这个功能已迁到 [Outreach 页面](/outreach)，更好用"轻量提示
- chat empty state 升级：第一行加 "管理 outreach pipeline →" 链接

**测试**：
- vitest：popup 默认只显示 25 项（30 - 5）
- 手动跑通：输 `/email` → 看到 banner，点链接跳转

**估时**：0.5 天 · **大小**：~120 行

---

### PR 8 — Chat ↔ Workspace 双向链接 [P1-7]
**目的**：让用户在 chat / workspace 间无缝切换。

**改动**：
- Chat 顶部加 "📊 Outreach" 快捷按钮（旁边可加 "📋 Watchlist"）
- Outreach 页右上角加 "💬 在 chat 里讨论" 按钮，跳回 chat 并预填 context
- Outreach 行点击 "在 chat 讨论这条" → 新 chat 带 outreach context

**测试**：
- 手动跑通：chat → outreach → 回 chat 带上下文

**估时**：1 天 · **大小**：~200 行

---

### PR 9 — 完成率埋点 [P1-8]
**目的**：量化 Phase 1 是否成功。

**改动**：
- 新建 `api/routers/analytics.py`（如不存在）：
  - `POST /api/analytics/event` — 通用埋点
  - `GET /api/analytics/outreach-funnel` — 漏斗统计（draft → sent → replied → signed）
- 前端：outreach compose / send / import-reply 各埋点
- admin 页加 "Outreach Funnel" 卡片（仅 admin 可见）
- 基线快照：跑当前数据，存为 baseline_2026_05_01.json

**测试**：
- pytest：埋点写入正确
- admin 能看到 funnel 数

**估时**：1 天 · **大小**：~250 行

---

### PR 10 — 文档 + 用户教育 [收尾]
**目的**：把 workspace 化的事告诉用户。

**改动**：
- `frontend/src/app/docs/content.ts`：
  - 新增章节 "Outreach Workspace（NEW）"
  - 标记 5 个 C 类 slash 为 "deprecated, use [outreach page]"
  - 更新 slash 命令清单（25 个分析/流程 + 5 个 deprecated）
- 登录后第一次进 chat 弹 onboarding tip："试试新的 Outreach 页面"
- `CHANGELOG.md`（如无则建）：记录这次重大变更

**测试**：
- 手动看文档渲染
- onboarding tip 仅首次出现

**估时**：0.5 天 · **大小**：~200 行

---

## 排期表

| 周 | PR | 累计 |
|---|---|---|
| W1 D1 | PR 1（slash 标签） | 0.5d |
| W1 D1-2 | PR 2（outreach API） | 2d |
| W1 D3-4 | PR 3（outreach 页面） | 4d |
| W1 D5 + W2 D1 | PR 4（compose 表单） | 6d |
| W2 D2-3 | PR 5（paste reply modal） | 7.5d |
| W2 D3-4 | PR 6（batch email） | 9d |
| W2 D4 | PR 7（C 类隐藏） | 9.5d |
| W2 D5 | PR 8（双向链接） | 10.5d |
| W2 D5 | PR 9（埋点） | 11.5d |
| W2 D5 | PR 10（文档） | 12d |

总计 **12 工作日**（含 buffer 算 2 工作周）。

---

## 验收标准（2 周末复盘）

- [ ] Slash popup 项数 30 → 25（C 类完全隐藏）
- [ ] `/outreach` 页面可用 + 有数据
- [ ] Compose 表单可生成 + 自动 log + 出现在 pipeline
- [ ] Paste-reply modal 可解析 + 归档
- [ ] Batch email 至少跑通 3 收件人案例
- [ ] Outreach funnel 仪表盘有基线数据
- [ ] 至少 3 个真实用户试用 + 给出反馈
- [ ] 文档更新 + CHANGELOG 记录

---

## Go/No-Go 决策（Sprint 末）

**指标 GREEN（继续 Phase 2）**：
- Outreach 完成率 ≥ baseline +20%
- ≥ 3/5 用户偏好 workspace > chat slash

**指标 YELLOW（调整后续 phase 设计）**：
- 完成率持平 / 略升，但用户反馈混合

**指标 RED（回退 + 重设计）**：
- 完成率下降 / 用户抗拒
- 启用 PR 7 的 banner 隐藏开关，重新评估

---

## 依赖检查

- [ ] Postgres 有 outreach_log 表（已有）
- [ ] watchlist API 模式可参考（已有）
- [ ] OutreachListService 输出结构稳定（已有）
- [ ] 前端 vitest infra 就绪（PR #133 已加）
- [ ] 不阻塞当前用户：所有改动向下兼容

---

**版本**：v1.0（2026-04-27）
**状态**：未开始 → 进行中 → 完成（每完成一个 PR 来这里勾掉）

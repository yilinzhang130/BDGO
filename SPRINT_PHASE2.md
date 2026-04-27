# Sprint: Phase 2 — Sell-side Workspace「我要卖」

**目标**：把"卖资产"从散落在 chat 里的 11 个 slash 收纳成一个产品级 workspace。
**对应 ROADMAP**：Phase 2（4 周）
**起始日期**：2026-04-28
**目标完成**：2026-05-25

---

## 当前状态

- ✅ 后端：`/api/outreach/*` 全套、`/api/analytics/*`、所有 11 个 B 类 slash 服务都能跑
- ✅ /outreach 工作台已上线（compose / paste-reply / pipeline / chat 双向）
- ✅ Watchlist 页 + 后端 CRUD
- ✅ Asset detail 页（基础版，chat-only 入口）
- ❌ 没有"卖方流程"作为一级心智入口
- ❌ B 类 slash（buyers / teaser / dd / faq / meeting / dataroom / draft-\*）依然是 chat-only
- ❌ Asset → outreach pipeline 没有可见关联
- ❌ Chat 讨论结论无法"采纳到资产"

---

## 设计原则

1. **资产是中心**：所有卖方流程围绕"一个资产"展开。从 BP 上传或选已有资产开始，结束于"签了"。
2. **Chat = 思考伙伴，Workspace = 流程引擎**：chat 解决"我该问什么"，workspace 解决"我下一步做什么 + 在哪存"。
3. **Form > Free-text prompt**：B 类 slash 失败的核心是"参数太多 prompt 拼不全"。表单天然解决。
4. **保留兼容**：B 类 slash 不删，只是 popup 默认隐藏 + workspace 主推。已有 chat 用户不受影响。

---

## 顶层架构

```
/sell                         （新顶级路由）
├── /sell                     资产看板（grid / list 切换）
├── /sell/upload              BP 上传 → intake plan（已有逻辑挪过来）
├── /sell/[assetId]           单资产 detail（升级现有 /assets/[id]）
│   ├── /buyers               反向匹配 + 挑选 buyer
│   ├── /teaser               生成 teaser + 按 buyer 定制变体
│   ├── /dd                   DD 准备时间线（dd seller + faq + meeting）
│   ├── /dataroom             数据室 checklist
│   ├── /drafts               5 个 draft-* 表单
│   └── /pipeline             这个资产的 outreach 历史（关联 /outreach 数据）
└── （未来：/sell/projects/[id]   多资产打包成 project，Phase 3）
```

---

## PR 拆分（10 个 PR，每个 ≤ 500 行）

### PR 1 — 顶级 /sell 路由 + 资产看板 [P2-1]

**目的**：建/sell 顶层导航 + 卖方资产列表入口。

**改动**：
- 新建 `frontend/src/app/sell/page.tsx`：grid 视图 / list 视图切换，每张卡显示资产名 + 阶段 + 适应症 + 上次更新 + 已外联 N 家
- 新建 `frontend/src/app/sell/layout.tsx`：左侧 nav (资产 | 看板 | 上传)，右侧内容区
- 后端：`/api/sell/assets` 返回当前用户的资产列表 + 关联 outreach 计数（复用现有 assets 表 + outreach_db.count_events）
- Sidebar.tsx：新增"我要卖"图标 + 链接，放在 Outreach 上方
- locale: zh + en `nav.sell` 等
- 数据基线：抓当前 assets 表的 user 自有资产数

**测试**：
- vitest：路由渲染 + grid/list toggle
- pytest：/api/sell/assets endpoint
- 手动：sidebar 点 "我要卖" 看到资产卡

**估时**：2 天 · **大小**：~450 行

---

### PR 2 — Asset detail 页升级（/sell/[id]）[P2-2]

**目的**：把现有 /assets/[id] 升级为 sell-side workspace 主页面，5 个流程子页签都从这里挂。

**改动**：
- 新建 `frontend/src/app/sell/[assetId]/layout.tsx`：顶部资产卡 + 6 个 tab (Overview / Buyers / Teaser / DD / Dataroom / Drafts)，再下面 nested route
- 新建 `frontend/src/app/sell/[assetId]/page.tsx`（Overview tab）：
  - 资产关键字段（target / indication / phase / mechanism）
  - "状态时间线"（什么时候被加进来 → 上次 outreach → 上次报告 → 下一步建议）
  - 关联的 outreach pipeline mini-view（5 行）
  - "在 chat 讨论这个资产" 按钮
- 把 chat 已有的资产元数据抽取（`asset_extract.py`）输出 wired 到这个页面
- 老路由 /assets/[id] 保留并加 banner: "新版在 /sell/[id]，更全面 →"

**测试**：
- vitest：tab nav 渲染
- 手动：进 /sell/[assetId] 看到 6 tab + Overview 内容

**估时**：2.5 天 · **大小**：~500 行

---

### PR 3 — Buyers tab：Match buyers 表单 [P2-3 / S2-01]

**目的**：替代 `/buyers` slash。资产页内点 "Match buyers" → 自动用资产参数填表 → 一键生成 → 结果落在 buyers tab。

**改动**：
- `/sell/[assetId]/buyers/page.tsx`
- 表单字段（自动用资产 metadata 预填）：target / indication / phase / top_n / 偏好（按 deal_size / 治疗领域 / 地区）
- "运行匹配" 按钮 → POST /api/reports/run slug=buyer-matching
- 结果 table：买方公司 + 匹配理由 + 历史 deal + 下一步行动按钮（"加入 outreach 列表" / "生成 teaser 给这家"）
- "加入 outreach 列表" → 创建 N 条 outreach_log status=draft
- 简单 vitest

**测试**：
- 手动：上传 BP → 进 /sell/[id]/buyers → 一键 Match → 看到 top 10 buyer
- 验证：点 "加入 outreach 列表" 后 /outreach 页能看到新增 draft

**估时**：3 天 · **大小**：~500 行

---

### PR 4 — Teaser tab + per-buyer 定制 [P2-4 / S2-02]

**目的**：替代 `/teaser` slash + 解决 S2-02（同一 teaser 发不同 buyer 一模一样）。

**改动**：
- `/sell/[assetId]/teaser/page.tsx`
- 表单：受众类型 (MNC / mid-pharma / VC) + 强调点 (efficacy / safety / IP / commercial) + 语言 (en/zh) + 长度 (one-pager / two-pager)
- 生成按钮 → POST /api/reports/run slug=deal-teaser
- 结果区：markdown preview + "下载 .docx" + "下载 .pptx"
- 新增 "按 buyer 定制" 区：
  - 选已 match 的 buyer → "为 X 定制" → 复用 base teaser + 加该 buyer 偏好提示重新生成
  - 历史变体列表（哪 buyer 看的哪版）
- 后端：teaser 生成不需要改，只是参数化

**测试**：
- 手动：选资产 → 生成基础 teaser → 选 Pfizer → 看到 Pfizer 版有差异化措辞

**估时**：3 天 · **大小**：~480 行

---

### PR 5 — DD tab：会议 + FAQ + 时间线合并 [P2-5 / S3-03 / S3-04 升级]

**目的**：把 `/dd seller` + `/faq` + `/meeting` 三个 slash 整合为一条"DD 准备时间线"。

**改动**：
- `/sell/[assetId]/dd/page.tsx`
- 时间线视图：从"准备 CDA" → "数据室开放" → "对方 DD 提问" → "面对面会议" → "出具决定"
- 每个里程碑挂功能卡：
  - "生成 dd-checklist"（seller 视角）
  - "预生成 FAQ"（按对方关注点）
  - "生成 meeting-brief"（按会议时间 + 对手）
- 每个卡可独立运行 + 结果留存 + "导出 PDF" / "复制到剪贴板"

**测试**：
- 手动：进 DD tab → 跑 checklist → 跑 FAQ → 跑 meeting brief → 看到三份输出留在时间线

**估时**：3 天 · **大小**：~500 行

---

### PR 6 — Dataroom tab：checklist 视图 [P2-6 / S4-01 升级]

**目的**：把 `/dataroom` 的 markdown 输出升级为可勾选的 checklist + 文件占位。

**改动**：
- `/sell/[assetId]/dataroom/page.tsx`
- "生成清单" → POST /api/reports/run slug=data-room → 拿到分类后的清单（Clinical / CMC / IP / Reg / Quality / Commercial / Financial）
- 清单 UI：每条 = 文件名 + checkbox（已准备/未准备）+ "上传文件占位" 区（不真传，记录 url）+ 备注
- 状态持久化：新表 `dataroom_items(asset_id, category, name, status, file_url, notes)`
- 后端新 endpoints：
  - `GET /api/sell/assets/{id}/dataroom`
  - `PATCH /api/sell/assets/{id}/dataroom/{item_id}`（更新 status / notes / file_url）
- "数据室就绪审计"按钮：跑统计（已准备 / 未准备 / 关键缺失）
- Alembic 迁移

**测试**：
- 手动：生成清单 → 勾选 → 刷新页面状态保留
- pytest：dataroom_items endpoints

**估时**：4 天 · **大小**：~500 行（前端 350 + 后端 150）

---

### PR 7 — Drafts tab：5 个 draft-\* 表单 [P2-7 / S5-S6 升级]

**目的**：替代 5 个 `/draft-*` slash 的 prompt 拼接，改为表单驱动。

**改动**：
- `/sell/[assetId]/drafts/page.tsx`
- 顶部选 draft 类型 (TS / MTA / License / Co-Dev / SPA)
- 每种 draft 一个独立表单（共用 base：交易方 + 资产标的，独立：upfront / milestone / royalty / territory / field / term...）
- "生成草案" → POST /api/reports/run slug=draft-{type}
- 结果区：markdown preview + 下载 .docx + "改参数重新生成" + "存为版本 v1"
- 版本历史侧栏：v1 / v2 / v3...
- 不需要后端改动（已有 draft-\* 服务）

**测试**：
- 手动：选资产 → 选 Term Sheet → 填 upfront $50M + royalty 10% → 生成 → 改 upfront $75M → v2
- vitest：表单字段切换

**估时**：3.5 天 · **大小**：~500 行

---

### PR 8 — "采纳到 workspace" 双向同步 [P2-8]

**目的**：chat 里讨论的结论一键写入 workspace。

**改动**：
- ChatMessage（assistant 消息）右下角加 "📥 采纳到资产" 按钮
- 点击 → 弹小 modal：选目标资产（从用户的 sell-side 资产列表）+ 选保存位置（资产备注 / Buyers tab / DD tab / Dataroom 项）+ 编辑后保存
- 后端：复用现有 asset notes / 各 tab 的 update endpoint
- 反向：资产页 "在 chat 讨论这个资产" → 跳 chat 带 ?context=asset&asset_id=X，ChatInputBar 已有 context 条机制（PR #159）扩展支持 asset

**测试**：
- 手动：chat 里聊了 KRAS G12D 资产分析 → 采纳到 workspace → 进资产页看到笔记

**估时**：2.5 天 · **大小**：~400 行

---

### PR 9 — Asset → Outreach pipeline 关联 [P2-9]

**目的**：在资产页能看到这个资产相关的所有 outreach 历史。

**改动**：
- 后端：outreach_log 表加 `asset_id` 字段（nullable）+ 迁移
- /api/outreach/events GET 加 `?asset_id=` 参数
- /api/outreach/events POST body 加 asset_id（可选）
- compose 表单加"关联资产"select（选了就带 asset_id）
- 资产 Overview tab + Pipeline mini-view 调 GET /api/outreach/events?asset_id=X
- 历史数据迁移：尝试通过 asset_context 文本匹配回填 asset_id（best-effort）

**测试**：
- pytest：filter by asset_id
- 手动：compose 邮件时选资产 → 进资产页看到那条 outreach

**估时**：2 天 · **大小**：~350 行

---

### PR 10 — Slash B 类 popup 隐藏 + 文档 + Playwright smoke [P2-收尾]

**目的**：B 类 slash 从 popup 默认隐藏（同 Phase 1 P1-7 模式）+ 用户文档更新 + 加 5 个 Playwright smoke 测进 CI。

**改动**：
- ChatInputBar 的 `hideCategories` 扩展为 `["B", "C"]`
- 输入 B 类 alias 时 banner: "💡 这个功能已迁到 [/sell/{assetId}/{tab}]"，含智能跳转
- docs/content.ts：新增 "Sell-side Workspace" 章节，B 类 12 个 slash 标 [迁出中]
- 新建 `frontend/playwright.config.ts` + `frontend/tests/smoke/` 5 个测：
  - login → /sell 看到资产卡
  - /sell/[id] 6 个 tab 都能切换
  - /outreach pipeline 渲染
  - chat 输 /paper 看到 popup（A 类还在）
  - chat 输 /buyers 看到 banner（B 类已迁）
- CI workflow：playwright job

**测试**：
- Playwright 5/5 通过
- 文档页面渲染无乱码

**估时**：2.5 天 · **大小**：~400 行

---

## 排期表

| 周 | PR | 主题 |
|---|---|---|
| W1 D1-2 | PR 1 | /sell 顶级路由 + 资产看板 |
| W1 D3-5 | PR 2 | /sell/[id] detail + 6 tab 框架 |
| W2 D1-3 | PR 3 | Buyers tab |
| W2 D4 + W3 D1-2 | PR 4 | Teaser tab + per-buyer 定制 |
| W3 D3-5 | PR 5 | DD tab |
| W4 D1-3 + W3 D5 | PR 6 | Dataroom tab + DB 表 + endpoints |
| W4 D3-5 | PR 7 | Drafts tab |
| W4 D5 + W5 D1 | PR 8 | "采纳到 workspace" |
| W5 D2 | PR 9 | Asset → Outreach 关联 |
| W5 D3 | PR 10 | B 类隐藏 + 文档 + Playwright |

总计 **20 工作日**（4 工作周 + 1 天 buffer）。

并行机会：
- PR 3 / 4 / 5 / 6 / 7 都是独立 tab 子页，PR 2 完成后可 4 个 session 并行
- PR 1 + PR 9（小后端）可并行
- PR 10（文档 + smoke）可与 PR 7 并行

实际并行执行预估：**12-15 工作日**（约 3 周）。

---

## 验收标准（Sprint 末复盘）

- [ ] /sell 顶级入口可见，sidebar 有 "我要卖"
- [ ] 上传 BP → 30 分钟内能完成 "Match buyers → Generate teaser → 起草 TS" 完整闭环
- [ ] B 类 12 个 slash 从 popup 隐藏，输入时 banner 引导到对应 tab
- [ ] 5 Playwright smoke 测进 CI，全绿
- [ ] 至少 3 个真实卖方用户试用 + 给反馈
- [ ] 量化：Lead time（BP → TS）较 chat-only 缩短 ≥40%
- [ ] CHANGELOG + ROADMAP §3 标 Phase 2 完成

---

## Go/No-Go 决策（Sprint 末）

**GREEN（继续 Phase 3 Buy-side）**：
- 卖方流程跑通完整闭环
- ≥3/5 用户偏好 workspace > chat slash
- Lead time 缩短 ≥40%

**YELLOW（修补后再决定）**：
- 闭环跑通但用户反馈混合（要继续打磨 vs 启动 Phase 3）

**RED（回退 + 重设计）**：
- 用户抗拒 workspace
- B 类 slash 隐藏后用户骂街找回来

---

## 风险

| 风险 | 缓解 |
|---|---|
| Asset 数据 schema 已固化，新增 asset_id 关联到 outreach 需要回填历史 | best-effort 回填，新数据走新字段 |
| 6 tab UI 太重，用户找不到东西 | tab 先做 4 个核心（Buyers / Teaser / DD / Dataroom），Drafts + Overview 灰度上 |
| Per-buyer teaser 变体存哪 | 新表 teaser_variants(asset_id, buyer_company, version, markdown_url) |
| Playwright 加 CI 之后 dev 卡 | smoke 测控制在 5 条 + ≤30s |

---

## 硬性指令（来自 RETRO_PHASE1）

1. ✅ 每个并行 brief 必含 `git worktree add ../bdgo-pX -b ... origin/main`
2. ✅ 每个 brief 收尾段必含完整 lint pipeline
3. ✅ 不强 merge — CI 红就修
4. ✅ Sprint 末写 RETRO_PHASE2.md
5. ✅ Playwright smoke 进 CI（PR 10）
6. ✅ 部署 + 抓基线 + 复盘三件事 1 周内完成

---

**版本**：v1.0（2026-04-27）
**下次更新**：Phase 2 W1 末（约 2026-05-04）调整剩余 PR 排序

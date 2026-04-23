---
name: review-structure
description: 审查 BDGO 代码库的结构性问题 — 分层、耦合、模块边界、命名一致性、死代码、循环依赖。当用户说"审查结构"、"看看架构"、"检查分层"、"review structure"、"structure review"时触发。不做安全/性能审查（分别用 /security-review、/review-performance）。
---

# Structure Review — BDGO

## 目的

给 BDGO 做**可复现**的结构审查。同样的代码 + 同样的 rubric → 不同 session 跑出来的 finding 应该高度重合。LLM 不临场发挥、只按清单走。

## 项目背景（决定 rubric 口径）

**后端** (`api/`, FastAPI):
- `routers/` — HTTP 层（22+ 文件）
- `services/` — 业务逻辑层（当前偏薄：`report_builder.py` + `reports/` + `helpers/`）
- `api/` 根目录 .py — 基础设施 / 领域混合层（`database.py`, `db.py`, `crm_db.py`, `crm_store.py`, `models.py`, `auth.py`, `credits.py`, `field_policy.py`, `planner.py`, `rate_limit.py`, `llm_pool.py` …）
- `conferences/` — 独立业务子包

**前端** (`frontend/src/`, Next.js App Router):
- `app/` — 路由 + 页面
- `components/` — 复用组件
- `hooks/` — React hooks
- `lib/` — 工具 / API client

## 执行顺序（严格按步）

### Step 1 — 机器审查打底（必跑，不跳）

```bash
cd api && ruff check . ; mypy . ; pytest --collect-only -q
cd ../frontend && pnpm lint ; pnpm tsc --noEmit
```

把这些输出作为"下限 finding"。LLM **不要**重复报告它们已经报过的东西。

### Step 2 — 读历史 finding（避免重复发现）

若 `docs/review-findings.md` 存在，先全文读。标 `done` / `wontfix` / `false-positive` 的条目**不再报告**，除非证据有变化。

### Step 3 — 按 rubric 逐项走

每一项必须给出结论：`PASS` / `WARN` / `FAIL` / `N/A`。`FAIL` 必须附证据（文件:行号）和建议动作。不允许跳项。

#### A. 分层完整性
- **A1** router 是否只做 HTTP 入参校验、调用 service、组装响应？业务逻辑写在 router 里算 FAIL
- **A2** service 层是否承担主要业务逻辑？若逻辑散落在 router / `api/` 根目录 .py，记 FAIL 并指出应迁移目的地
- **A3** DB 访问是否集中？`database.py` / `db.py` / `crm_db.py` / `crm_store.py` 四个文件职责边界是否清晰、不重叠？命名相似是危险信号
- **A4** router 是否直接触达 ORM / 原生 SQL？应经 service / repository
- **A5** Pydantic schema（入参/出参）vs SQLAlchemy model（持久化）是否严格分离

#### B. 模块耦合
- **B1** 跨模块导入方向：router → service → db。反向或跨层导入算 FAIL
- **B2** 是否存在循环导入？用 `python -c "import <module>"` 或 `pydeps` 验证
- **B3** `config.py` 是否被到处直接读魔法常量？应通过注入或封装
- **B4** 前端 `components/` 是否依赖 `app/` 下的页面专属代码？（应单向：app 用 components，反之不行）
- **B5** `lib/` 是否被 `components/` 和 `hooks/` 都依赖？方向是否一致

#### C. 命名一致性
- **C1** 路由文件名 vs URL 前缀（`assets.py` ↔ `/assets`）
- **C2** `crm_db.py` / `crm_store.py` / `db.py` / `database.py` 能否一眼区分？不能则 FAIL 并建议重命名
- **C3** 前端 hooks 是否都 `use*` 开头
- **C4** `utils.py` / `helpers.py` / `common.py` / `misc.py` 这类语义空洞模块是**结构腐化信号**，逐个检查内容是否能拆分

#### D. 模块边界
- **D1** `routers/chat/` 已拆子目录 — 其他 router 若超过 500 行也应拆分，列出候选
- **D2** `conferences/` 子包边界是否清晰（自有 service + schema + router）
- **D3** 跨业务域是否通过 service API 交互，而非直读对方 DB 表
- **D4** `services/helpers/` 是否变成了杂货箱

#### E. 死代码与重复
- **E1** 有无 `_old` / `_backup` / `_v2` / 大段注释掉的代码 → 列出
- **E2** 两个 router 是否实现几乎相同的逻辑（复制粘贴信号）
- **E3** 同一 SQL / 业务规则在 ≥ 2 处重复 → 列出
- **E4** 未被任何地方 import 的模块 / 函数（用 `grep -r "from .X import" ` 或 `vulture`）

#### F. 测试结构
- **F1** `api/tests/` 是否镜像 `api/` 目录结构
- **F2** 是否有"只验 200 不验业务结果"的伪测试（扫描 `assert response.status_code == 200` 之后没有更多断言的用例）
- **F3** service 层是否有独立单元测试，还是只有通过 router 的集成测试

### Step 4 — 固定输出格式

```
## Structure Review — <date> — <commit-sha>

### Machine checks (下限)
- ruff:    N errors / M warnings
- mypy:    ...
- eslint:  ...
- tsc:     ...
- pytest collect: ... (是否有 collection error)

### Rubric findings

- [A3][FAIL][high] api/crm_db.py 与 api/crm_store.py 职责重叠
  证据: crm_db.py:42 定义 get_company(); crm_store.py:18 也定义 get_company()，签名不同但语义相同
  建议: 合并到 crm_store.py；crm_db.py 改为仅提供连接/会话管理
  影响面: 所有 router 的 import 语句

- [C4][WARN][medium] api/services/helpers/ 为语义空洞命名
  证据: 目录下有 X 个文件，涵盖 A/B/C 三类不相关功能
  建议: 按领域拆分为 services/<domain>/

### Summary
FAIL: X (high: N, medium: M) | WARN: Y | PASS: Z | N/A: W
Top 3 需立即处理:
1. ...
2. ...
3. ...
```

### Step 5 — 沉淀到 findings 台账

新 finding 追加到 `docs/review-findings.md`（不存在则**提示用户**是否创建，不要擅自建目录）。台账格式：

```md
| ID | Date | Scope | Rubric | Severity | Status | File:Line | Summary |
|----|------|-------|--------|----------|--------|-----------|---------|
| S-001 | 2026-04-23 | structure | A3 | high | open | api/crm_db.py:42 | crm_db 与 crm_store 职责重叠 |
```

状态词汇固定：`open` / `in-progress` / `done` / `wontfix` / `false-positive`。

## 严重度判定（统一口径）

- **high**: 真实 bug 风险 / 数据损坏可能 / 循环依赖 / 分层彻底破坏 / 安全边界模糊
- **medium**: 结构坏味道、后续会导致 bug、命名混乱、重复代码 ≥ 3 处
- **low**: 纯风格、收益小的重构、单处命名不佳

## 明确不做

- ❌ 不做安全审查 → `/security-review`
- ❌ 不做性能审查 → 另建 `review-performance` skill
- ❌ **不修改代码**，只出报告
- ❌ 不 `git commit` / `git push`
- ❌ 不重复机器审查已经报出的 lint / type 错误

## 升级规则（什么时候停下问用户）

- 发现 ≥ 3 个 `high` 级 FAIL 且看起来相互关联 → 停下来先确认要不要做一次架构层级重构再继续审查，避免出一堆相互矛盾的建议
- rubric 某项需要用户回答领域问题才能判定（如"这两个模块是不是故意分开的"）→ 问一次，不要猜

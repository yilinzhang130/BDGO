---
name: review-performance
description: 审查 BDGO 的性能与可扩展性问题 — LLM 调用效率、并发正确性、DB 查询、缓存、热点路径、前端渲染。当用户说"审查性能"、"看看慢在哪"、"扛不扛得住并发"、"review performance"、"perf review"时触发。不做结构/可维护性/API/安全审查（分别用对应 /review-* 或 /security-review skill）。
---

# Performance Review — BDGO

## 目的

给 BDGO 做**可复现**的性能审查。项目的硬约束是"扛 20+ 并发 + MiniMax 配额天花板"，所以 rubric 偏重 **LLM 调用效率、async 正确性、DB 查询**这三块。不走"感觉这里可能慢"路线，每项必须有证据或可复现实验。

## 项目背景（决定 rubric 口径）

**扩展性目标**: 单实例扛 20+ 并发用户，演进到 agent swarm。
**硬天花板**: MiniMax API 配额（每个 LLM 调用都要当贵资源算账）。

**性能关键路径** (`api/`):
- `llm_pool.py` — LLM 调用池 / 复用 / 速率控制
- `rate_limit.py` — 接口限流
- `planner.py` — agent 规划（可能是热点）
- `routers/chat/` — 长响应、流式
- `services/report_builder.py` + `reports/` — 长任务
- `crm_db.py` / `crm_store.py` / `database.py` / `db.py` — DB 访问
- `conferences/` — 批量数据处理可能的大户

**前端** (`frontend/src/`):
- `app/` — SSR/CSR、路由级 code-split
- `components/` — 重渲染来源
- `hooks/` — 数据获取 & 缓存

## 执行顺序（严格按步）

### Step 1 — 机器信号打底（必跑）

性能的"机器下限"比结构/lint 弱，但仍要先跑能跑的：

```bash
# 后端
cd api
ruff check . --select PERF,ASYNC,SIM     # perf / async / simplify（ruff 已覆盖语法检查，无需 compileall）
pytest -q --durations=20                 # 最慢的 20 个用例，看有没有 > 1s 的单测
grep -rn "time.sleep\|requests\.\|urllib" --include="*.py" . | head -50   # 同步阻塞调用在 async 里 = 大问题
grep -rn "\.all()\b" --include="*.py" . | head -50                        # SQLAlchemy .all() 高危（N+1 / 全表）

# 前端
cd ../frontend
npm run lint
npx tsc --noEmit
# bundle 大小不在 Step 1 默认跑（`npm run build` 30s+）；需要 F7 数据时手动跑：
#   npm run build 2>&1 | tail -40
#   可选：npx @next/bundle-analyzer
```

**这些输出中已经报出的问题，LLM 不要重复报告**，只补机器看不到的。

### Step 2 — 读历史 finding

若 `docs/review-findings.md` 存在，读取 scope=`performance` 的条目。`done` / `wontfix` / `false-positive` 的不再报。

### Step 3 — 按 rubric 逐项走

每项给 `PASS` / `WARN` / `FAIL` / `N/A`。FAIL 需附证据（文件:行号 + 为什么慢/贵 + 改进动作）。不允许跳项。

#### A. 并发正确性（async）
- **A1** `async def` 函数内是否调用了**同步阻塞 I/O**（`requests.*`、`urllib`、阻塞 DB driver、`time.sleep`、同步文件读写）？这是 async FastAPI 的头号性能杀手
- **A2** CPU 密集任务是否放在 `run_in_executor` / 线程池，而不是直接占用事件循环？
- **A3** `async with` / `async for` 是否正确使用，没有把 async 资源当同步用
- **A4** 有没有在 async 路径里用 `asyncio.run()` 二次启动事件循环（致命错误）
- **A5** 并发扇出（`asyncio.gather`）是否限流？无限 fan-out 会把外部 API 打爆

#### B. LLM 调用（BDGO 核心，严格）
- **B1** `llm_pool.py` 是否对**相同 prompt + 参数**做结果缓存？重复计算 = 烧 MiniMax 配额
- **B2** 是否使用 **prompt caching**（Anthropic / 支持的 provider）？长 system prompt 不做 caching 是硬伤
- **B3** 是否有**请求合并 / 批量**机制？多个用户的相似请求能否合并
- **B4** 超时 + 重试策略：是否有指数退避？是否会把短暂故障放大成雪崩
- **B5** 是否区分**必须 LLM** 和**规则可解**的路径？（凡是能用正则/SQL 搞定的不该走 LLM）
- **B6** 流式响应：长回答是否用 streaming 而不是等全部生成完才返回
- **B7** token 预算：每个 session 是否有 token 上限，防止单用户把配额烧光
- **B8** `planner.py` 是否被每个请求都重跑？结果能否缓存 / memoize
- **B9** 并发 LLM 调用是否有池上限？无限并发会秒触 MiniMax rate limit

#### C. 数据库
- **C1** N+1 查询：循环里是否调用 DB？列出所有可疑位点（for 循环体内有 `.query()` / `.filter()` / `session.get()`）
- **C2** `SELECT *` / `.all()` 无 limit 加载大表 → 列出
- **C3** 是否有缺失索引的证据？高频 WHERE 字段、JOIN 字段、ORDER BY 字段是否都在 `schema.sql` / alembic migrations 里建了索引
- **C4** 连接池配置：`database.py` / `db.py` 的 pool_size / max_overflow / pool_pre_ping 是否适配 20+ 并发
- **C5** 长事务 / 锁：是否有跨 LLM 调用的事务（请求期间持锁 → 并发立刻崩）
- **C6** 只读查询是否用 autocommit / 避免不必要的事务包裹
- **C7** 批量写入是否用 `bulk_insert_mappings` / `execute(values)` 而不是循环 `session.add()`

#### D. 缓存
- **D1** 哪些数据是"读多写少" + "计算贵"？这些位点是否有缓存（内存 / Redis / 磁盘）
- **D2** 缓存是否有 TTL 和失效策略？（无 TTL 会导致数据陈旧 bug）
- **D3** HTTP 响应是否设置合理 `Cache-Control` / `ETag`？静态/半静态数据不 cache 是浪费
- **D4** 前端 SWR / react-query（如有）的 staleTime / cacheTime 是否合理配置

#### E. 网络与外部依赖
- **E1** 外部 API 调用（除 LLM 外）是否有超时？无超时 = 一次下游慢 = 全系统卡死
- **E2** 是否用了 `httpx.AsyncClient` 的**复用实例**，而不是每次请求新建 client（TCP 建连成本）
- **E3** DNS / TLS 握手：是否启用 keep-alive
- **E4** 文件 `upload.py`：大文件是否流式处理而不是全读进内存

#### F. 前端性能
- **F1** Next.js 路由是否用 Server Components / streaming（App Router 能用的都用了吗）
- **F2** `use client` 边界是否合理？整页 client 化是反模式
- **F3** `'use client'` 文件是否导入了沉重的 lib（日期库、图表库）而不 lazy-load
- **F4** 图片是否用 `next/image`（自动优化 + lazy）
- **F5** API 请求瀑布：多个独立请求是否并行（`Promise.all` / 并行 loader）而非串行
- **F6** Key / memo：列表 key 是否稳定；高开销组件是否 `memo` / `useMemo`
- **F7** Bundle：`npm run build` 输出的最大 chunk 是否 > 300KB gzipped（Step 1 未默认跑，需用户手动采集）

#### G. 可观测性（不做就无法持续审查）
- **G1** 请求延迟 p50/p95/p99 是否有打点？没打点 = 所有"慢"的判断都是猜
- **G2** LLM 调用是否记录 tokens_in / tokens_out / latency / cost？（配额管理的基础）
- **G3** DB 慢查询日志是否启用（PG: `log_min_duration_statement`）
- **G4** 有无错误率 / 限流触发率的监控？

#### H. 资源与限流
- **H1** `rate_limit.py` 的粒度是否合理（per-user / per-endpoint / global）？
- **H2** 有没有**后台任务**占用 worker（例如长报告生成）阻塞 HTTP 请求处理？应该进队列（RQ / Celery / asyncio task）
- **H3** 内存泄漏信号：全局 dict / list 无清理、缓存无上限

### Step 4 — 固定输出格式

```
## Performance Review — <date> — <commit-sha>

### Machine signals (下限)
- ruff PERF/ASYNC/SIM: N hits
- pytest slowest tests: <list top 5 with durations>
- 同步 I/O in async suspects: <count>
- .all() 无 limit 可疑: <count>
- frontend bundle largest chunk: X KB gzipped
- build warnings: ...

### Rubric findings

- [B1][FAIL][high] llm_pool.py 无结果缓存
  证据: llm_pool.py:<line> 每次调用直连 provider，key 中不含缓存命中检查
  影响: MiniMax 配额浪费，20 并发下 p95 预计 +Xs
  建议: 按 (model, prompt_hash, params_hash) 做 LRU + TTL 缓存；热 prompt 单独记
  验证: 实现后用 locust/ab 跑 50 并发，对比 tokens_used

- [C1][WARN][medium] routers/reports.py 怀疑 N+1
  证据: reports.py:<line> for company in companies: session.query(Asset).filter(Asset.company_id==company.id)
  建议: selectinload / joinedload 一次 JOIN

### Summary
FAIL: X (high: N, medium: M) | WARN: Y | PASS: Z
预计对"扛 20 并发 + MiniMax 配额"影响最大的 Top 3:
1. ...
2. ...
3. ...

### Benchmark 建议（可选）
- 若有 high FAIL，给出 1-2 个可跑的基准命令（locust / ab / pytest-benchmark 脚本片段）让用户验证修复前后差距
```

### Step 5 — 沉淀到 findings 台账

追加到 `docs/review-findings.md`，scope=`performance`，ID 前缀 `P-xxx`。Schema / 状态词汇 / Severity 口径以 findings.md 为单一真源。

## 严重度判定（遵循 findings.md；下面是 perf 专用具体判据）

- **critical**: 单点会直接打爆 MiniMax 配额（无缓存 + 无限流 + 热路径）/ 20 并发下立即崩
- **high**: 会在 20 并发下触发 MiniMax 限流 / 打崩服务 / p95 > 5s / 同步阻塞在 async 代码里 / 无 timeout 的外部调用 / N+1 在热路径
- **medium**: 稳态下能跑但浪费配额或资源、p95 > 2s、N+1 在冷路径、前端 bundle 超标
- **low**: 微优化、仅影响单用户体感、收益 < 5%

## 明确不做

- 不做结构/命名审查 → `/review-structure`
- 不做可维护性审查 → `/review-maintainability`
- 不做安全审查 → `/security-review`
- **不修改代码**，只出报告 + benchmark 建议
- 不跑耗时 > 30s 的基准测试（建议用户手动跑）
- 不重复机器审查已经报出的问题

## 升级规则

- 若 `G` 类（可观测性）多项 FAIL → **停下来先建议补打点**，没数据的"性能审查"大多是猜测，先让数据说话再审查有更高信噪比
- 若发现单点会直接打爆 MiniMax 配额（例如无缓存 + 无限流 + 热路径）→ 标 `critical`，建议立即修复再继续审查其他项

---
name: review-api-design
description: 审查 BDGO 的对外 API 契约 — URL 设计、HTTP 语义、错误响应格式、请求/响应 schema、分页、幂等、版本化、认证边界、限流响应、长任务/流式契约、OpenAPI 质量、跨端点一致性。当用户说"审查 API 设计"、"看看接口契约"、"检查 API 一致性"、"review api design"、"api contract review"时触发。不做结构/性能/安全/可维护性审查（分别用对应 skill）。
---

# API Design Review — BDGO

## 目的

审查**对外契约** — 客户端（前端 / 第三方 / 将来的 agent swarm）看到的东西。产品上线前把契约定好，上线后改契约的代价是指数级的（兼容期、客户端版本、文档、SDK 全都要跟）。

和其他 skill 的分工：
- `/review-structure` — 内部分层（不关心契约形状）
- `/review-performance` — 跑得多快（不关心响应格式）
- `/review-maintainability` — 代码内部卫生（不关心对外体验）
- `/security-review` — 安全漏洞（不关心 REST 风格）
- **本 skill** — 客户端体验 + 契约稳定性 + 跨端点一致性

## 项目背景

**后端** (`api/routers/`): 22+ 路由文件，覆盖 admin / auth / api_keys / assets / buyers / catalysts / chat / clinical / companies / conferences / credits / deals / inbox / ip / reports / search / sessions / stats / tasks / upload / watchlist / write。

**特殊端点类型**:
- `routers/chat/` — 已拆子包（streaming、tool-loop、compaction…），**流式/长对话契约重灾区**
- `routers/reports.py` + `services/report_builder.py` — **长任务**，需要异步契约（202 / job id / 轮询或 webhook）
- `routers/upload.py` — 文件上传契约（大小、类型、分片）
- `routers/api_keys.py` — 给第三方 / 自己的 SDK 用，契约稳定性要求最高
- `routers/watchlist.py` / `stats.py` — 列表类端点，分页/排序/筛选契约
- `rate_limit.py` — 限流的**响应契约**（429 + Retry-After + 配额 header）

**前端** (`frontend/src/lib/`): API client 是契约的实际消费者，审查时对照看。

## 执行顺序

### Step 1 — 导出 OpenAPI + 机器信号

```bash
cd api

# 1. 导出当前 OpenAPI spec
python -c "from main import app; import json; print(json.dumps(app.openapi(), indent=2))" > /tmp/openapi.json 2>/dev/null \
  || echo "WARN: OpenAPI 导出失败，检查 main.py"

# 2. 结构化统计端点
python -c "
import json
spec = json.load(open('/tmp/openapi.json'))
paths = spec.get('paths', {})
total = sum(len(methods) for methods in paths.values())
print(f'Total endpoints: {total}')
print(f'Total paths: {len(paths)}')
# 列出各 HTTP 方法计数
from collections import Counter
methods = Counter()
for p, ms in paths.items():
    for m in ms:
        methods[m.upper()] += 1
print('By method:', dict(methods))
"

# 3. Spectral lint（可选但推荐）
# npx @stoplight/spectral-cli lint /tmp/openapi.json --ruleset spectral:oas

# 4. 直接信号
grep -rEn "@router\.(get|post|put|patch|delete)" --include="*.py" routers/ | wc -l
grep -rEn "raise HTTPException" --include="*.py" . | wc -l           # 错误抛出总数
grep -rEn "status_code\s*=\s*[0-9]+" --include="*.py" routers/ | sort -u | head -30   # 散布的状态码
grep -rEn "response_model\s*=" --include="*.py" routers/ | wc -l     # 带 response_model 的端点数
grep -rEn "@router\.(get|post|put|patch|delete)[^)]*\)" --include="*.py" routers/ | wc -l  # 端点总数
# 两者差值 = 没声明响应 schema 的端点数

# 5. URL 风格一致性信号（取前 80 条扫风格，够判断混用即可）
grep -rEn '@router\.(get|post|put|patch|delete)\("([^"]+)"' --include="*.py" routers/ | awk -F'"' '{print $2}' | sort -u | head -80
# 人眼扫：有没有混用 /assets vs /asset、下划线 vs 横杠、大小写

# 6. 前端 API client 调用点
cd ../frontend
grep -rEn "fetch\(|axios\.|\.post\(|\.get\(" --include="*.ts" --include="*.tsx" src | wc -l
```

### Step 2 — 读历史 finding

读 `docs/review-findings.md` 中 scope=`api-design` 的条目。

### Step 3 — 按 rubric 逐项走

每项给 `PASS` / `WARN` / `FAIL` / `N/A`。FAIL 附证据（文件:行 + URL + 问题描述）。

#### A. URL 与资源建模
- **A1** 资源名是否一致（复数 `/assets` vs 单数 `/asset` 不混用）
- **A2** 命名风格是否统一（kebab-case / snake_case 选一个）
- **A3** 嵌套深度 ≤ 2（`/companies/{id}/assets` 可以；`/companies/{id}/assets/{id}/catalysts/{id}/...` 应拍平）
- **A4** URL 里是否混入动词（`/getCompany` / `/listAssets` 是 FAIL；应该 `GET /companies` + `GET /companies/{id}`）
- **A5** 查询参数 vs 路径参数：识别资源用路径，过滤/分页/排序用 query
- **A6** ID 格式一致（全用 UUID / 全用 int，不混用）
- **A7** 是否有 orphan URL（端点存在但前端 client 无调用）

#### B. HTTP 方法与状态码语义
- **B1** `GET` 是否**安全幂等**（不改数据库状态）— 扫 `@router.get` 函数体有无 `session.add/commit`
- **B2** `PUT` 是否全量替换、`PATCH` 是否部分更新（不能反着用）
- **B3** `DELETE` 是否幂等（重复调用结果一致）
- **B4** **状态码匹配语义**：
  - 创建资源 → 201（很多项目错用 200）
  - 异步受理 → 202
  - 资源未找到 → 404（不是 400 / 200+error）
  - 未认证 → 401 / 未授权 → 403（常被搞混）
  - 冲突 → 409
  - 限流 → 429
  - 入参校验失败 → 422（FastAPI 默认）
- **B5** 成功删除：204（无 body）或 200（带 body），不要 FAIL 掉重复删除
- **B6** 不要在 200 里塞 `{"error": ...}` —— 错误必须用 4xx/5xx

#### C. 错误响应契约（客户端能不能程序化处理错误）
- **C1** 所有错误响应是否用**同一种 JSON 形状**（推荐 RFC 7807 Problem Details 或一致的 `{code, message, details}`）
- **C2** 是否有**机器可读错误码**（`INSUFFICIENT_CREDITS` / `RATE_LIMITED` / `ASSET_NOT_FOUND`），不是只给人读的 message
- **C3** 错误信息是否**可行动**（告诉客户端能做什么），而不是 "failed" / "error"
- **C4** `HTTPException(detail=...)` 的 detail 是否结构化（dict）而非纯字符串
- **C5** 是否泄漏内部细节（堆栈、SQL、文件路径、密钥）到错误响应
- **C6** 校验错误（422）是否带**字段定位**（FastAPI 默认带，自定义的不要丢失）
- **C7** 限流错误（429）是否带 `Retry-After` header

#### D. 请求 / 响应 schema 卫生
- **D1** 所有端点是否声明 `response_model`（不声明 = 契约不稳定）
- **D2** 请求体是否用独立 Pydantic schema（不直接用 ORM model）
- **D3** 输入/输出 schema 是否严格分离（`AssetCreate` vs `AssetRead` vs `AssetUpdate`），不是同一个类
- **D4** 字段必填 / 可选是否准确（`Optional[X]` vs `X | None` 与 default 配合正确）
- **D5** 是否有意外泄漏字段（password_hash、internal_note 进了响应）
- **D6** 时间字段是否统一用 ISO 8601 + UTC
- **D7** 金额 / credits 字段单位是否明确（是"个"还是"美分"？在字段名或文档里讲清）
- **D8** 枚举值是否用 str Enum 而不是裸 int / 字符串字面量

#### E. 分页、筛选、排序
- **E1** 列表端点（`/assets`、`/companies`、`/watchlist` 等）**全部**支持分页？无分页 = 20 并发下翻大列表会爆内存
- **E2** 分页方式一致（**全部**用 offset/limit 或 **全部**用 cursor，不混）
- **E3** 默认 limit 和最大 limit 是否定义（防止客户端传 limit=10000）
- **E4** 返回体是否含总数 / next_cursor / has_more
- **E5** 排序参数命名一致（`sort=-created_at` / `order_by=created_at&order=desc` 选一个）
- **E6** 筛选参数命名一致（`status=active` vs `filter[status]=active` 选一个风格）

#### F. 幂等性与并发
- **F1** 写操作（POST 创建、付费类）是否支持 `Idempotency-Key` header？支付 / credits 扣费类**必须**支持
- **F2** 重试安全：网络重试同一请求不会重复扣费 / 重复创建
- **F3** 乐观并发：更新端点是否用 `If-Match` / `ETag` 或 version 字段防止 lost update
- **F4** `DELETE` 重复删除：是否返回 204（幂等）而不是 404（不幂等但有人这么做，需明确选择）

#### G. 版本化与向后兼容
- **G1** 是否有版本策略（`/v1/...` URL 前缀 / `Accept: application/vnd.bdgo.v1+json` header）
- **G2** 破坏性变更的处理流程是否明确（废弃 → 双写 → 切换 → 下线）
- **G3** 是否用 `Deprecation` / `Sunset` header 标记待废弃端点
- **G4** OpenAPI 里是否标了 `deprecated: true` 的端点及下线日期

#### H. 认证 / 授权契约
- **H1** 每个端点的认证要求是否明确（公开 / 需 session / 需 api key / 需 admin）
- **H2** 前端友好的认证错误：401 触发登录重定向；403 告知"无权限"
- **H3** API key 认证：key 是否经 header（`Authorization: Bearer` 或 `X-API-Key`）而非 query string（泄漏到日志）
- **H4** 权限边界：`routers/admin.py` 是否有路由级 `Depends(require_admin)`，不能靠单函数内部 if 判断
- **H5** 多租户 / 用户边界：所有读写是否带 `current_user.id` 过滤，防止越权读其他用户数据（IDOR）
- **H6** `routers/aidd_sso.py` SSO 流程的 state / nonce / redirect_uri 校验是否规范

#### I. 限流作为契约
- **I1** 429 响应是否带 `Retry-After`
- **I2** 是否暴露配额 header（`X-RateLimit-Limit` / `-Remaining` / `-Reset`）让客户端自我管理
- **I3** 限流触发的错误码是否**机器可读**（`RATE_LIMITED`）
- **I4** 不同端点的限流粒度是否记录在 OpenAPI description 里

#### J. 长任务 / 流式 / 异步契约
- **J1** `routers/reports.py` 的长任务：是否用 **202 Accepted + Location header + GET /tasks/{id}** 轮询模式，而不是让 HTTP 挂 30 秒
- **J2** 任务状态是否标准化（`pending` / `running` / `succeeded` / `failed` / `cancelled`）
- **J3** 任务取消：是否有 DELETE / POST `/tasks/{id}/cancel` 端点
- **J4** `routers/chat/sse.py` / `streaming.py`：SSE 契约是否稳定（事件类型、心跳、结束标记、错误中断）
- **J5** 流式响应遇到错误：是否通过 SSE `event: error` 传递，而不是中途断 TCP
- **J6** WebSocket（如有）的 ping/pong / 重连协议是否定义

#### K. OpenAPI / 文档质量
- **K1** 每个端点是否有 `summary` + `description`（不是留空）
- **K2** 每个端点是否声明 `responses={200, 4xx, 5xx}` 带 schema（不是只默认 200）
- **K3** 关键端点是否带 `examples`（请求体 + 响应）
- **K4** 错误响应 schema 是否在 OpenAPI 里有专门定义并引用
- **K5** `routers/__init__.py` / `main.py` 是否给路由分 tag（OpenAPI 文档按功能分组）
- **K6** 是否维护一份 API Changelog（人类可读的变更记录）

#### L. 跨端点一致性（契约最大的毛病）
- **L1** 同一概念在不同端点里字段名是否一致（`user_id` vs `userId` vs `uid` 不能混）
- **L2** 同类端点的响应结构是否一致（所有列表端点都是 `{items, total, next_cursor}`？还是有的裸数组有的包一层？）
- **L3** 时间戳字段命名一致（`created_at` 全局统一，不要半数端点用 `createdTime`）
- **L4** 布尔字段命名一致（`is_active` / `active` 选一个）
- **L5** `routers/chat/` 子路由之间的契约是否自洽（不因为内部拆分导致对外不一致）

### Step 4 — 固定输出格式

```
## API Design Review — <date> — <commit-sha>

### Machine signals
- Endpoints: N  (GET: a, POST: b, PUT: c, PATCH: d, DELETE: e)
- response_model 覆盖: X/N (Y%)
- HTTPException 使用: N 处
- 散布的原始 status_code 数值: N 种
- Spectral lint（若跑）: N errors / M warnings
- 前端 API 调用点: N

### Rubric findings

- [C1][FAIL][high] 错误响应形状不一致
  证据: routers/credits.py:42 返回 {"error": "..."}；routers/assets.py:88 返回 {"detail": "..."}；routers/search.py:120 裸字符串
  建议: 统一为 {code: str, message: str, details: dict?}，或用 RFC 7807
  影响: 前端无法用统一错误拦截器；SDK 生成困难

- [F1][FAIL][high] credits 扣费端点无 Idempotency-Key
  证据: routers/credits.py POST /credits/charge 无 Idempotency-Key 头处理
  建议: 增加 Idempotency-Key 读取 + 24h 去重表
  风险: 前端重试或断网重发 = 重复扣费

- [J1][WARN][medium] reports 端点可能长时间阻塞
  证据: routers/reports.py POST /reports 同步调用 report_builder
  建议: 改为 202 + /tasks/{id} 轮询模式
  客户端影响: 30s+ 请求，代理/网关超时风险

- [L1][WARN][medium] 字段命名不一致
  证据: assets.py 用 company_id; deals.py 用 companyId
  建议: 全项目锁定 snake_case

### Summary
FAIL: X (high: N, medium: M) | WARN: Y | PASS: Z
上线前必修（high）: <list>
上线后可逐步改（medium/low）: <list>
```

### Step 5 — 沉淀到台账

追加 `docs/review-findings.md`，scope=`api-design`，ID 前缀 `A-xxx`。Schema / 状态词汇 / Severity 口径以 findings.md 为单一真源。

**API 契约 finding 必填**: `BreaksClient` 列填 `yes` / `no` —— 上线后修复会不会让现有客户端坏，决定修复窗口是"上线前"还是"下个大版本"。

## 严重度判定（遵循 findings.md；下面是 api-design 专用具体判据）

- **critical**:
  - F1 失败在 credits / billing / 支付相关端点（财务风险：重复扣费）
  - H5 越权（IDOR），任一端点缺 `current_user.id` 过滤
  - H3 API key 走 query string（日志泄漏）
- **high**:
  - 错误响应格式混乱到客户端无法做统一处理
  - 支付 / credits 类写操作无幂等保护（非财务端点）
  - 长任务把 HTTP 卡死超 30s
  - 状态码用错（在 200 里返回错误、delete 后返回 200 说 "not found"）
- **medium**:
  - 命名不一致 / 字段风格混用
  - 分页缺失 / 不统一
  - OpenAPI 描述缺失
  - 无版本策略
- **low**:
  - 文档细节 / example 缺失
  - 个别 summary 写得含糊

## 明确不做

- 不做结构审查 → `/review-structure`
- 不做性能审查 → `/review-performance`
- 不做可维护性审查 → `/review-maintainability`
- 不做安全漏洞审查 → `/security-review`（但 H5 IDOR / H3 API key 通过 query 等涉及"契约级安全"仍在本 skill 范围）
- **不修改代码**，只出报告
- 不跑端到端集成测试（建议用 schemathesis 让用户手动跑）

## 升级规则

- 若发现 **C 类（错误契约）全面混乱** → 停下来建议**先定一份 API Conventions 文档**（错误格式、命名、分页、版本策略），后续 finding 才有统一判据
- 若发现 **F1 失败在 credits/billing 相关端点** → 标 `critical` 单独列，这是财务风险
- 若发现 **H5 (IDOR)** 任何一处 → 标 `critical`，同时建议跑 `/security-review` 做全面授权边界检查
- 若 **L 类（跨端点一致性）FAIL 过多**（> 10 处）→ 一次性修复风险高，建议分批次处理并更新 `API Conventions.md`

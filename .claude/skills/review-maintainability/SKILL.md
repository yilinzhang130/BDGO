---
name: review-maintainability
description: 审查 BDGO 的可维护性与长期技术债 — 死代码、魔法数、抽象泄漏、伪测试、文档腐化、错误处理可调试性、migration 债务、复杂度热点。当用户说"审查可维护性"、"看看代码债"、"技术债盘点"、"review maintainability"、"清理屎山"时触发。不做结构/性能/API/安全审查（分别用对应 /review-* 或 /security-review skill）。
---

# Maintainability Review — BDGO

## 目的

盘点**长期债务**。这些项目不会让系统崩或慢，但时间一长会让改动变慢、bug 变多、新人上手变难。比结构/性能审查更偏"健康体检"，产出的 finding 允许慢慢清。

和 `/review-structure` 的区别：**结构审**分层/耦合/边界（宏观），**可维护性审**代码内部卫生 + 信号质量（微观）。两者互补、不重叠。

## 项目背景

**后端** (`api/`):
- `tests/` 已分 `unit/` / `integration/` / `security/` — 测试结构看起来规整，要验证其实质
- `migrations/versions/` — alembic 迁移，久了易留死 migration / 孤儿 revision
- 根目录 .py 多（`auth.py`, `credits.py`, `field_policy.py`, `planner.py` …）— 每个文件的内部卫生都要体检

**前端** (`frontend/src/`):
- `components/` / `hooks/` / `lib/` — 是死代码和重复的高发区

## 执行顺序

### Step 1 — 机器信号打底（尽量自动化）

```bash
# 后端
cd api
ruff check . --select C90,ERA,PLR,TRY,RET,ARG,PIE,SIM    # 复杂度 / 注释掉的代码 / pylint重构 / try卫生 / 死参数
grep -rn "TODO\|FIXME\|XXX\|HACK\|hack\|tmp\|temporary" --include="*.py" . | wc -l
grep -rn "^# " --include="*.py" . | grep -iE "deprecated|legacy|old" | head -30
grep -rEn "^\s*(print|pdb\.set_trace|breakpoint)\b" --include="*.py" . | head -50   # 忘删的调试语句
pytest --collect-only -q > /tmp/pytest-collect.out 2>&1 ; tail -5 /tmp/pytest-collect.out ; wc -l < /tmp/pytest-collect.out   # 收集错误 + 数量（单次调用）
# 可选：pip install vulture radon interrogate
# vulture api/ --min-confidence 80
# radon cc api/ -a -nb                                                    # 复杂度 B 级以下
# interrogate -vv api/                                                    # docstring 覆盖

# 前端
cd ../frontend
npm run lint
grep -rn "TODO\|FIXME\|XXX\|HACK" --include="*.ts" --include="*.tsx" src | wc -l
grep -rEn "console\.(log|debug)" --include="*.ts" --include="*.tsx" src | head -50   # 忘删的 console
# 可选：npx ts-prune    # 未使用导出
# 可选：npx depcheck    # 未使用依赖

# migration 健康
ls api/migrations/versions/ | wc -l
grep -l "^def upgrade" api/migrations/versions/*.py | while read f; do grep -c "pass" "$f"; done | sort -u    # 空 migration
```

**机器已报出的不重复报告。**

### Step 2 — 读历史 finding

读 `docs/review-findings.md` 中 scope=`maintainability` 的条目。

### Step 3 — 按 rubric 逐项走

每项给 `PASS` / `WARN` / `FAIL` / `N/A`。FAIL 需附证据。

#### A. 死代码与未使用
- **A1** 未被任何地方 import 的模块（grep `from .X import` / `import X` 全仓库验证）
- **A2** 定义后无人调用的函数 / 类（vulture 可辅助，但有误报，需人工确认）
- **A3** 大段被注释掉的代码（超过 5 行注释块）→ 列文件:行
- **A4** `_old` / `_v1` / `_backup` / `_deprecated` 后缀命名的文件或函数
- **A5** `if False:` / `if 0:` / 永远到不了的分支
- **A6** 前端未使用导出（`ts-prune` 信号）
- **A7** `package.json` / `requirements.txt` 里已不再用的依赖（`depcheck` / 手动搜 import）

#### B. 复杂度热点
- **B1** 单函数 > 80 行 → 列出并标复杂度
- **B2** 圈复杂度 > 10（radon C 级以上）→ 列 top 10
- **B3** 嵌套深度 > 4 层（if/for/try 套娃）→ 列出
- **B4** 单文件 > 500 行（不是硬线但值得看）→ 列出
- **B5** 参数 > 6 个的函数 → 考虑参数对象化

#### C. 魔法数 / 配置散落
- **C1** 代码中出现的**无名常量**（数字、字符串字面量）散布在多文件 → 应移到 `config.py` 或枚举
- **C2** 超时 / 重试次数 / 分页大小 / 速率限制值：是否硬编码？应配置化
- **C3** 业务阈值（credits 每次扣多少、token 预算 …）是否集中管理
- **C4** `os.environ.get("X", "default")` 散落各处而不是集中 `config.py` 读取
- **C5** 前端 API 基础 URL / 超时 / 重试策略是否硬编码在组件中

#### D. 抽象质量
- **D1** **抽象泄漏**：上层暴露了下层实现细节（例如 service 返回 SQLAlchemy Row 而不是 domain object）
- **D2** **过度抽象**：单用户 / 单实现的 ABC / Protocol / Strategy 基类 → 删除、直接用具体类
- **D3** **参数幽灵**：函数参数 `flag: bool` / `mode: str` 控制分支，多个这种参数应拆成多个函数
- **D4** 全局可变状态（模块级 `_cache = {}`、单例带 setter）→ 列出并评估
- **D5** `Any` / `object` 类型充当万金油（type hint 形同虚设）
- **D6** 前端：`any` 类型出现次数；过度 `as unknown as T` 强转

#### E. 测试质量（不是覆盖率，是信号）
- **E1** **伪测试**：`assert response.status_code == 200` 之后无业务断言 → 逐个列出
- **E2** **重复测试**：多个用例测几乎相同的路径 / 相同输入 → 合并候选
- **E3** **脆弱测试**：依赖时间（`datetime.now()` 未 freeze）、依赖网络、依赖顺序
- **E4** **无测试的关键模块**：对照 `api/` 关键文件（`llm_pool.py` / `planner.py` / `credits.py` / `field_policy.py` / `rate_limit.py` / `auth.py`）是否在 `tests/` 下有对应用例
- **E5** `integration/` 和 `unit/` 界限是否清晰（unit 不应起 DB / 网络）
- **E6** `conftest.py` fixture 是否失控膨胀
- **E7** 跳过的测试（`@pytest.mark.skip` / `xfail`）是否有 TODO 票据关联

#### F. 文档与注释
- **F1** public 函数 / class 的 docstring 覆盖率（interrogate 信号）
- **F2** README 是否描述**现状**（跑起来的命令、env 变量、部署流程）—— 不是 vision 宣言
- **F3** 注释是否解释 **why** 而不是 **what**（"# 增加 1" 这种注释是噪音）
- **F4** 注释是否和代码**一致**（代码改了注释没改 = 有毒注释）
- **F5** OpenAPI / FastAPI 路由的 `summary` / `description` / 响应 schema 是否填全
- **F6** ADR（架构决定记录）是否存在？重大决定（选哪个 DB、为什么用 MiniMax）有没有留记录

#### G. 错误处理与日志可调试性
- **G1** `except Exception:` 裸吞 → 列出
- **G2** `except:` 不带类型 → FAIL
- **G3** 异常信息是否**可行动**（包含 id / 关键字段 / context，不只是 "failed"）
- **G4** 日志层级是否合理（debug / info / warning / error 不混用）
- **G5** 日志是否带 **correlation id / request id**（出事能串起来）
- **G6** 是否把密钥 / token / PII 不小心写进日志
- **G7** 前端错误：是否有全局 error boundary；网络错误是否给用户**可行动**的提示

#### H. Migration 与技术债信号
- **H1** `migrations/versions/` 里是否有**空 migration**（只有 `pass`）→ 列出
- **H2** 是否有**孤儿 revision**（`down_revision` 链断裂）
- **H3** 是否有数据迁移和 schema 迁移混在一起（难回滚）
- **H4** `schema.sql` 和 alembic 最终状态是否一致（两份真源 = 迟早不一致）
- **H5** TODO/FIXME/XXX/HACK 总数是否在增长？是否有关联 issue / 截止日期
- **H6** 是否有**已知 bug 用 try/except 绕过**的注释（`# workaround for xxx`）未追踪

#### I. 命名与代码卫生（细节层）
- **I1** 变量名 `tmp` / `data` / `obj` / `x` / `y` 在超过单次简短使用范围内出现
- **I2** 布尔变量 / 函数是否 `is_*` / `has_*` / `should_*` 命名
- **I3** 前端组件文件名 vs 组件名是否一致
- **I4** 缩写滥用（`usr_ctx_mgr` 这种）

### Step 4 — 固定输出格式

```
## Maintainability Review — <date> — <commit-sha>

### Machine signals
- ruff C90/ERA/PLR/TRY 命中: <counts by category>
- TODO/FIXME/XXX/HACK: backend N, frontend M
- 遗留 print/console.log: N
- 测试收集: X ok / Y errors
- 空 migration: N
- (可选) vulture dead code candidates: N
- (可选) radon 复杂度 ≥ C: N 个函数
- (可选) ts-prune 未使用导出: N

### Rubric findings

- [E1][FAIL][high] 伪测试集中在 tests/integration/test_reports.py
  证据: test_reports.py:23/45/67 仅断言 status_code==200 无业务检查
  建议: 至少断言响应 JSON 的关键字段 + DB 副作用
  修复工作量: 小

- [H1][WARN][medium] 空 migration 存在
  证据: migrations/versions/abc123_placeholder.py 仅有 pass
  建议: 删除或补上实际变更；确认 down_revision 链完整

- [C3][FAIL][medium] credits 扣费阈值硬编码
  证据: credits.py:42 扣 5 credits; routers/chat.py:88 扣 10 credits
  建议: 移到 config.py:CREDITS_COST dict，集中维护

### Summary
FAIL: X (high: N, medium: M) | WARN: Y | PASS: Z
Top 5 清理 ROI（投入小、收益大）:
1. ...
```

### Step 5 — 沉淀到台账

追加到 `docs/review-findings.md`，scope=`maintainability`，ID 前缀 `M-xxx`。Schema / 状态词汇 / Severity 口径以 findings.md 为单一真源。可维护性 finding 的特点是"可以慢慢清"，每条务必填 **Effort** 列（S/M/L）便于未来排期。

## 严重度判定（遵循 findings.md；下面是 maintainability 专用具体判据）

- **critical**: `except Exception: pass` 吞在关键路径（auth / credits / rate_limit）/ 日志误记密钥或 PII / 有毒注释直接掩盖 bug
- **high**: 已在误导当前开发（伪测试掩盖 bug / 裸 except 吞关键错误 / 注释与代码不一致）
- **medium**: 增加改动成本（死代码 / 复杂度热点 / 散落魔法数 / 抽象泄漏）
- **low**: 纯卫生（命名不佳 / 单处风格问题 / 细节文档缺失）

## 明确不做

- 不做结构审查 → `/review-structure`
- 不做性能审查 → `/review-performance`
- 不做安全审查 → `/security-review`
- **不修改代码**，只出报告
- 不因为"我觉得不够优雅"就报 FAIL —— 必须能说清为什么影响维护

## 升级规则

- 若 **E 类（测试质量）多项 FAIL** 且 `assert response.status_code == 200` 是主流模式 → 停下来建议先做**测试质量专项整改**，不然后续 review 拿不到可靠信号
- 若 `TODO/FIXME/XXX/HACK` 总数 > 源码文件数 → 建议建立 TODO 追踪流程（每个 TODO 关联 issue），本次只列 top-20 最可疑的
- 若发现 `except Exception: pass` 吞在关键路径（auth / credits / rate_limit）→ 标 `critical` 单独列

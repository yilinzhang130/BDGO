# Review Findings — BDGO

四个 review skill 的**共用台账**，是本仓库 Schema / 状态词汇 / Severity 口径的单一真源。Skill 在审查前读此文件，跳过已标 `done` / `wontfix` / `false-positive` 的条目。

---

## 使用方式

1. Skill 跑完会把新 finding 追加到 `Open` 节。
2. 你人工判断每条 finding 的真伪和优先级。
3. 状态流转：
   - `open` → `in-progress`（开始修）
   - `in-progress` → `done`（修完合并）
   - `open` → `wontfix`（确认不修，留原因）
   - `open` → `false-positive`（LLM 误报，删也行但留着教训更好）
4. 修完的 finding **保留在文件里**（移到 `Done` 节），不要删 —— 这是你的"审查记忆"。

---

## Schema

| 列 | 说明 |
|---|---|
| **ID** | 形如 `S-001` (structure) / `P-001` (performance) / `M-001` (maintainability) / `A-001` (api-design)，递增不复用 |
| **Date** | 首次发现日期 (YYYY-MM-DD) |
| **Scope** | `structure` / `performance` / `maintainability` / `api-design` |
| **Rubric** | 对应 skill 的 rubric 编号 (A1 / B3 / ...) |
| **Severity** | `critical` / `high` / `medium` / `low` |
| **Status** | `open` / `in-progress` / `done` / `wontfix` / `false-positive` |
| **Effort** | `S` (<1h) / `M` (半天~1天) / `L` (>1天) |
| **BreaksClient** | 仅 api-design：`yes` / `no` / `n/a` (修复会不会影响已部署客户端) |
| **File:Line** | 主要证据位置 |
| **Summary** | 一句话描述 |
| **Notes** | 状态变更原因、关联 PR / issue、修复思路 |

---

## Severity 统一口径

- **critical**: 财务 / 安全 / 数据损坏 / 上线即炸 → 立即处理
- **high**: 会在目标负载下出问题 / 误导当前开发 / 契约硬错
- **medium**: 增加成本、风险可控，但该修
- **low**: 卫生问题、微优化

---

## Open

<!-- Skill 追加区。示例：
| S-001 | 2026-04-23 | structure | A3 | high | open | M | n/a | api/crm_db.py:42 | crm_db 与 crm_store 职责重叠 | 两处都定义 get_company，签名不同语义相同 |
-->

| ID | Date | Scope | Rubric | Severity | Status | Effort | BreaksClient | File:Line | Summary | Notes |
|----|------|-------|--------|----------|--------|--------|--------------|-----------|---------|-------|

---

## In-Progress

| ID | Date | Scope | Rubric | Severity | Status | Effort | BreaksClient | File:Line | Summary | Notes |
|----|------|-------|--------|----------|--------|--------|--------------|-----------|---------|-------|

---

## Done

| ID | Date | Scope | Rubric | Severity | Status | Effort | BreaksClient | File:Line | Summary | Notes (PR/commit) |
|----|------|-------|--------|----------|--------|--------|--------------|-----------|---------|-------------------|

---

## Wontfix

| ID | Date | Scope | Rubric | Severity | Status | Effort | BreaksClient | File:Line | Summary | Notes (why not fixing) |
|----|------|-------|--------|----------|--------|--------|--------------|-----------|---------|------------------------|

---

## False-Positive

（保留误报记录，便于识别 LLM 的系统性误判模式。）

| ID | Date | Scope | Rubric | File:Line | Why False-Positive |
|----|------|-------|--------|-----------|---------------------|

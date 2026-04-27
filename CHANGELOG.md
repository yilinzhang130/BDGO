# Changelog

All notable changes to BD Go will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Outreach 工作台（即将上线）**：新增独立外联工作台，整合 pipeline 看板视图、Compose 写信表单、粘贴回信解析、批量外联发送，替代现有 5 个外联 slash 命令，提供全流程可视化外联管理体验。
- **`ROADMAP.md` 与 `SPRINT_PHASE1.md` 公开**：产品路线图与 Phase 1 冲刺计划文档现已对外发布，用户可查看各阶段规划与进展。

### Changed

- **Slash 命令类别标签**：所有 slash 命令增加类别标注（A 分析类 / B 流程类 / C 迁出类），方便用户快速定位所需命令。
- **`/email`、`/log`、`/outreach`、`/import-reply`、`/batch-email` 标记 [迁出中]**：以上 5 个外联相关 slash 命令将随 Outreach 工作台上线而隐藏，迁移期约 2 周，届时会在产品内添加 banner 提示。

[Unreleased]: https://github.com/bdgo-ai/bdgo/compare/HEAD...HEAD

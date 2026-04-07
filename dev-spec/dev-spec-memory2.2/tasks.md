# File-First Memory Traceability 2.2 Tasks

本文件从 [dev-spec-memory2.2.md](./dev-spec-memory2.2.md) 映射而来，按阶段拆分实现任务。

## Phase 1：Memory 模型与类型定义

- 状态：已完成
- 目标：定义 `memory/YYYY-MM-DD.md`、`memory.json` 扩展字段，以及 `MemoryGet` / `MemorySet` 语义
- 输入：现有 `memory.json`、coach memory 设计、前后端类型约束
- 输出：Markdown entry 约定、索引字段契约、读取写入抽象说明
- 依赖：无
- 完成定义（DoD）：
  - `memory/YYYY-MM-DD.md` 路径规则明确
  - entry 模板明确
  - `memory.json` 的 `sources` / `thread_ids` 字段定义明确
  - `MemoryGet` / `MemorySet` 语义明确
  - `coach_profile.json` 职责保持不变

## Phase 2：后端写入链路调整

- 状态：已完成
- 目标：让长期记忆先写 Markdown，再更新 `memory.json`
- 输入：memory updater、queue、prompt 注入流程
- 输出：Markdown append 能力、来源字段写回、双写链路约束
- 依赖：Phase 1
- 完成定义（DoD）：
  - 新记忆先落 Markdown
  - 新 facts 带 `sources` 与 `thread_ids`
  - summary section 带 `sources` 与 `thread_ids`
  - 无来源 entry 的索引写入被禁止
  - 现有 memory queue 流程不被破坏

## Phase 3：后端读取链路与下钻策略

- 状态：已完成
- 目标：明确何时读取 `memory.json`，何时下钻 `memory/YYYY-MM-DD.md`
- 输入：coach route、lead agent prompt、memory accessor 需求
- 输出：读取顺序、下钻条件、coach 优先级约束
- 依赖：Phase 2
- 完成定义（DoD）：
  - prematch 读取顺序符合 spec
  - health 读取顺序符合 spec
  - fallback/general 读取顺序符合 spec
  - 下钻原文条件在代码层可执行
  - `coach_profile.json` 优先级不被弱化

## Phase 4：查询与前端展示最小补齐

- 状态：已完成
- 目标：让前端 memory 页面具备最小来源查看能力
- 输入：`/api/memory` 返回结构、前端 memory 页面展示需求
- 输出：sources/thread_ids API 字段、来源展示与查看入口
- 依赖：Phase 3
- 完成定义（DoD）：
  - API 能返回 `sources` 与 `thread_ids`
  - 前端 memory 页面能显示来源信息
  - facts 能展示 thread 引用
  - summary 能展示 entry 引用

## Phase 5：回归与验收

- 状态：已完成
- 目标：验证该架构满足“可追溯、可审阅、可重建”
- 输入：memory 测试、coach 测试、双写链路结果
- 输出：回归测试、验收结论、重建路径说明
- 依赖：Phase 4
- 完成定义（DoD）：
  - `memory.json` 与 Markdown 双写链路通过
  - 至少一个 fact 可回指 thread
  - 至少一个 summary 可回指 entry
  - `memory.json` 注入格式兼容现有 prompt
  - 索引缺失时存在可重建路径
  - coach route 在读取时不会错误跳过 `coach_profile.json`

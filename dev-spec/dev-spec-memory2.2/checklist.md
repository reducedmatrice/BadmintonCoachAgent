# File-First Memory Traceability 2.2 Checklist

## Phase 1：Memory 模型与类型定义

- [x] `memory/YYYY-MM-DD.md` 路径规则明确
- [x] entry 模板明确
- [x] `memory.json` 的 `sources` / `thread_ids` 字段定义明确
- [x] `MemoryGet` / `MemorySet` 语义明确
- [x] `coach_profile.json` 职责保持不变

## Phase 2：后端写入链路调整

- [x] 新记忆先落 Markdown
- [x] 新 facts 带 `sources` 与 `thread_ids`
- [x] summary section 带 `sources` 与 `thread_ids`
- [x] 无来源 entry 的索引写入被禁止
- [x] 现有 memory queue 流程不被破坏

## Phase 3：后端读取链路与下钻策略

- [x] prematch 读取顺序符合 spec
- [x] health 读取顺序符合 spec
- [x] fallback/general 读取顺序符合 spec
- [x] 下钻原文条件在代码层可执行
- [x] `coach_profile.json` 优先级不被弱化

## Phase 4：查询与前端展示最小补齐

- [x] API 能返回 `sources` 与 `thread_ids`
- [x] 前端 memory 页面能显示来源信息
- [x] facts 能展示 thread 引用
- [x] summary 能展示 entry 引用

## Phase 5：回归与验收

- [x] `memory.json` 与 Markdown 双写链路通过
- [x] 至少一个 fact 可回指 thread
- [x] 至少一个 summary 可回指 entry
- [x] `memory.json` 注入格式兼容现有 prompt
- [x] 索引缺失时存在可重建路径
- [x] coach route 在读取时不会错误跳过 `coach_profile.json`

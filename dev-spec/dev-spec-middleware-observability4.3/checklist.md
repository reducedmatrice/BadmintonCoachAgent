# Middleware Observability 4.3 Checklist

## Phase 1：Trace Helper 与 Request Scope

- [x] 不同 `trace_id` 不再合并旧 steps
- [x] 业务 preview 上限提升到 500 字符
- [x] credentials key 继续过滤
- [x] `test_request_trace.py` 已覆盖

## Phase 2：Middleware Registry

- [x] 已新增 `TraceRegistryMiddleware`
- [x] 已输出 `middleware.registry`
- [x] registry 包含 middleware_order
- [x] registry 包含 conditional middleware 状态
- [x] coach agent entrypoint 测试已覆盖

## Phase 3：核心 Middleware Checkpoints

- [x] `middleware.thread_data` 可见
- [x] `middleware.uploads` 可见
- [x] `middleware.sandbox` 可见
- [x] `middleware.dangling_tool_call` 可见
- [x] `middleware.tool_error_handling` 可见
- [x] `middleware.coach_clarification` 可见
- [x] `middleware.title` 可见
- [x] `middleware.view_image` 可见
- [x] `middleware.deferred_tool_filter` 可见
- [x] `middleware.loop_detection` 可见
- [x] `middleware.clarification` 可见

## Phase 4：Memory Enqueue Observability

- [x] `middleware.memory` queued path 可见
- [x] `middleware.memory` skipped path 可见
- [x] raw/filtered/user/assistant counts 可见
- [x] queue_pending_before/after 可见
- [x] filtered user/assistant previews 可见

## Phase 5：Memory Writeback Structured Event

- [x] 已新增 `[MemoryStructured]` event
- [x] event 包含 entry_id / entry_path
- [x] event 包含 memory_file
- [x] event 包含 updated_sections
- [x] event 包含 new_facts preview
- [x] event 包含 facts_removed
- [x] event 包含 extracted_signals
- [x] `update_memory()` bool API 兼容

## Phase 6：ChannelManager 与 Structured Log 收口

- [x] structured log 只包含当前 trace_id steps
- [x] 缺失 major steps 使用 `status=unknown`
- [x] channel manager 测试已覆盖

## Phase 7：文档与验证

- [x] `docs/request-flow.md` 已更新
- [x] 快速 pytest 命令通过
- [x] `git diff --check` 通过
- [x] 已复核无 credentials / base64 / 完整附件内容进入日志

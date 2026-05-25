# Middleware Observability 4.3 Checklist

## Phase 1：Trace Helper 与 Request Scope

- [ ] 不同 `trace_id` 不再合并旧 steps
- [ ] 业务 preview 上限提升到 500 字符
- [ ] credentials key 继续过滤
- [ ] `test_request_trace.py` 已覆盖

## Phase 2：Middleware Registry

- [ ] 已新增 `TraceRegistryMiddleware`
- [ ] 已输出 `middleware.registry`
- [ ] registry 包含 middleware_order
- [ ] registry 包含 conditional middleware 状态
- [ ] coach agent entrypoint 测试已覆盖

## Phase 3：核心 Middleware Checkpoints

- [ ] `middleware.thread_data` 可见
- [ ] `middleware.uploads` 可见
- [ ] `middleware.sandbox` 可见
- [ ] `middleware.dangling_tool_call` 可见
- [ ] `middleware.tool_error_handling` 可见
- [ ] `middleware.coach_clarification` 可见
- [ ] `middleware.title` 可见
- [ ] `middleware.view_image` 可见
- [ ] `middleware.deferred_tool_filter` 可见
- [ ] `middleware.loop_detection` 可见
- [ ] `middleware.clarification` 可见

## Phase 4：Memory Enqueue Observability

- [ ] `middleware.memory` queued path 可见
- [ ] `middleware.memory` skipped path 可见
- [ ] raw/filtered/user/assistant counts 可见
- [ ] queue_pending_before/after 可见
- [ ] filtered user/assistant previews 可见

## Phase 5：Memory Writeback Structured Event

- [ ] 已新增 `[MemoryStructured]` event
- [ ] event 包含 entry_id / entry_path
- [ ] event 包含 memory_file
- [ ] event 包含 updated_sections
- [ ] event 包含 new_facts preview
- [ ] event 包含 facts_removed
- [ ] event 包含 extracted_signals
- [ ] `update_memory()` bool API 兼容

## Phase 6：ChannelManager 与 Structured Log 收口

- [ ] structured log 只包含当前 trace_id steps
- [ ] 缺失 major steps 使用 `status=unknown`
- [ ] channel manager 测试已覆盖

## Phase 7：文档与验证

- [ ] `docs/request-flow.md` 已更新
- [ ] 快速 pytest 命令通过
- [ ] `git diff --check` 通过
- [ ] 已复核无 credentials / base64 / 完整附件内容进入日志

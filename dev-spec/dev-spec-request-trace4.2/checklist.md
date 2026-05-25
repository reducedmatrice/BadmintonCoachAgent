# Request Trace 4.2 Checklist

## Phase 1：Request Trace 基础设施

- [x] 已新增 request trace helper
- [x] 已定义 `trace_id`
- [x] 已定义 step schema
- [x] 已实现 step 追加
- [x] 已实现 trace 合并
- [x] 已实现 summary 截断
- [x] 已实现敏感 key 过滤
- [x] `ThreadState` 已支持 `request_trace`

## Phase 2：Structured Log 输出

- [x] `[ManagerStructured]` 顶层包含 `request_trace`
- [x] `request_trace.trace_id` 可见
- [x] `request_trace.steps` 可见
- [x] 旧 structured log 字段保持兼容
- [x] result 缺失 trace 时有降级输出

## Phase 3：Middleware Trace

- [x] `middleware.multimodal` step 已覆盖 success
- [x] `middleware.multimodal` step 已覆盖 skipped/disabled/error
- [x] `middleware.coach_intake` step 已包含 intent 摘要
- [x] `middleware.coach_intake` step 已包含 clarification 摘要
- [x] `middleware.coach_intake` step 已包含 recall 摘要

## Phase 4：Router 与 Renderer Trace

- [x] `router.coach_route` step 已包含 route
- [x] `router.coach_route` step 已包含 persisted/writeback 摘要
- [x] `renderer.coach_response` step 已包含 response_length
- [x] `renderer.coach_response` step 已包含 has_recall_line
- [x] renderer 输出文本未因 trace 改变

## Phase 5：ChannelManager 串联

- [x] manager 已创建 `request_trace_id`
- [x] run_context 已注入 `request_trace_id`
- [x] 已记录 `channel.inbound`
- [x] 已记录 `manager.thread`
- [x] 已记录 `manager.upload_materialize`
- [x] 已记录 `manager.run_context`
- [x] 已记录 `manager.outbound`
- [x] error 分支已记录 `manager.error`

## Phase 6：测试与文档

- [x] `test_request_trace.py` 通过
- [x] `test_structured_logs.py` 通过
- [x] `test_coach_intake_middleware.py` 通过
- [x] `test_coach_single_intent_router.py` 通过
- [x] 必要的 channel manager 测试通过
- [x] `docs/request-flow.md` 已补充 request trace 说明
- [x] 已复核没有 secrets 或完整敏感内容进入 trace

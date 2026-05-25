# Request Trace 4.2 Tasks

本文件从 [dev-spec-request-trace4.2.md](./dev-spec-request-trace4.2.md) 映射而来，按阶段拆分实现任务。

## Phase 1：Request Trace 基础设施

- 状态：待开始
- 目标：建立统一 trace schema、helper 和 ThreadState 合并能力
- 输入：现有 `ThreadState`、structured log helper、coach state 字段
- 输出：`request_trace.py`、`ThreadState.request_trace`、基础单元测试
- 依赖：无
- 并行项：可与 Phase 2 的 structured log 测试设计并行
- 阻塞项：无
- 完成定义（DoD）：
  - 可生成稳定 `trace_id`
  - 可追加 `name / layer / status / timestamp_ms / summary`
  - 可合并多个 trace steps 且保持顺序
  - summary 字符串会截断
  - 敏感 key 不会进入 summary

## Phase 2：Structured Log 输出 request_trace

- 状态：待开始
- 目标：让 `[ManagerStructured]` 顶层包含 `request_trace`
- 输入：`backend/app/channels/structured_logging.py`
- 输出：`extract_request_trace()` 与 `build_run_log_record(..., request_trace=...)`
- 依赖：Phase 1
- 并行项：可与 Phase 3 的 middleware 接入并行
- 阻塞项：无
- 完成定义（DoD）：
  - result 有 `request_trace` 时原样规范化输出
  - result 无 trace 时输出传入的 manager trace
  - 旧 route/token/multimodal 字段不变
  - `test_structured_logs.py` 覆盖新增字段

## Phase 3：Middleware Trace 接入

- 状态：待开始
- 目标：记录多模态与 coach intake 的中间状态
- 输入：`CoachMultimodalIntakeMiddleware`、`CoachIntakeMiddleware`
- 输出：`middleware.multimodal`、`middleware.coach_intake` steps
- 依赖：Phase 1
- 并行项：可与 Phase 4 的 router/renderer 接入并行
- 阻塞项：无
- 完成定义（DoD）：
  - intake step 包含 intent、confidence、clarification、recall 摘要
  - multimodal step 包含 success/disabled/skipped/error 状态
  - middleware 返回值不会覆盖已有 trace steps
  - 相关单元测试通过

## Phase 4：Router 与 Renderer Trace 接入

- 状态：待开始
- 目标：记录 coach route 决策和最终渲染摘要
- 输入：`router.py`、`response_renderer.py`
- 输出：`router.coach_route`、`renderer.coach_response` steps
- 依赖：Phase 1
- 并行项：可与 Phase 3 并行
- 阻塞项：无
- 完成定义（DoD）：
  - router step 包含 route、intent_source、persisted/writeback 摘要
  - renderer step 包含 route、response_length、has_recall_line
  - 不改变现有 response text
  - 相关 router 测试通过

## Phase 5：ChannelManager 串联 Trace

- 状态：待开始
- 目标：把 channel、manager、middleware、router、renderer、outbound 串成一条 trace
- 输入：`backend/app/channels/manager.py`
- 输出：manager 侧 trace id 创建、run_context 注入、outbound step、error step
- 依赖：Phase 1-4
- 并行项：无
- 阻塞项：无
- 完成定义（DoD）：
  - `run_context` 包含 `request_trace_id`
  - non-streaming structured log 包含完整 trace
  - streaming final structured log 包含完整 trace
  - outbound step 包含 response/artifact/attachment/streaming 摘要
  - error 分支有 `manager.error`

## Phase 6：验证与文档回写

- 状态：待开始
- 目标：跑最快相关测试，并把 request-flow 文档补充 trace 说明
- 输入：新增代码和测试
- 输出：测试结果、`docs/request-flow.md` trace 章节
- 依赖：Phase 1-5
- 并行项：无
- 阻塞项：无
- 完成定义（DoD）：
  - 快速 pytest 命令通过
  - `docs/request-flow.md` 描述 request trace 输出位置和主要 steps
  - `checklist.md` 对应项完成
  - git diff 只包含 request trace 相关改动

# Middleware Observability 4.3 Tasks

本文件从 [dev-spec-middleware-observability4.3.md](./dev-spec-middleware-observability4.3.md) 映射而来，按阶段拆分实现任务。

## Phase 1：Trace Helper 与 Request Scope

- 状态：待开始
- 目标：让 request trace 支持更具体 preview，并解决跨 turn 历史 step 混入问题。
- 输入：`backend/packages/harness/deerflow/domain/coach/request_trace.py`
- 输出：新 merge 语义、新 preview limit、测试覆盖
- 完成定义（DoD）：
  - 不同 `trace_id` 的 trace 合并时不会继承旧 steps
  - 业务文本 preview 上限提升到 500 字符
  - credentials key 仍被过滤
  - `test_request_trace.py` 覆盖上述行为

## Phase 2：Middleware Registry

- 状态：待开始
- 目标：在每次 coach runtime 请求开始时记录实际 middleware 顺序。
- 输入：`coach_agent/agent.py`
- 输出：`TraceRegistryMiddleware` 与 `middleware.registry` step
- 完成定义（DoD）：
  - registry step 包含 `runtime=coach`
  - registry step 包含 middleware_order 和 count
  - conditional middleware 状态可见
  - `test_coach_agent_entrypoint.py` 覆盖 registry middleware 位置

## Phase 3：核心 Middleware Checkpoints

- 状态：待开始
- 目标：给基础 runtime middleware 增加轻量 trace step。
- 输入：thread_data、uploads、sandbox、dangling tool、tool error、coach clarification、title、view image、deferred tool、loop detection、clarification middleware
- 输出：对应 `middleware.*` steps
- 完成定义（DoD）：
  - 每个 step 有明确 status 和 reason
  - 不改变原业务返回
  - skips 也能被看见，至少 registry 能证明存在
  - 单元测试覆盖 thread_data、uploads、coach_clarification、memory 的代表路径

## Phase 4：Memory Enqueue Observability

- 状态：待开始
- 目标：让同步 request trace 看见 MemoryMiddleware 是否入队和入队内容摘要。
- 输入：`memory_middleware.py`、`memory/queue.py`
- 输出：`middleware.memory` step
- 完成定义（DoD）：
  - queued 时包含 raw/filtered/user/assistant counts
  - queued 时包含 queue_pending_before/after
  - queued 时包含 user/assistant preview
  - skipped 时包含 reason
  - 测试覆盖 enabled queued、disabled skipped、缺失 user/assistant skipped

## Phase 5：Memory Writeback Structured Event

- 状态：待开始
- 目标：让异步 memory updater 的真实写入结果可查。
- 输入：`memory/queue.py`、`memory/updater.py`
- 输出：`[MemoryStructured]` 事件和 result dataclass
- 完成定义（DoD）：
  - queue 使用详细 result 记录 success/skipped/error
  - event 包含 entry_id、entry_path、memory_file
  - event 包含 updated_sections、new_facts preview、facts_removed、extracted_signals
  - `update_memory()` bool API 兼容不破坏旧调用
  - 测试覆盖成功和失败事件

## Phase 6：ChannelManager 与 Structured Log 收口

- 状态：待开始
- 目标：最终 structured log 只显示当前请求 trace，并为缺失 major steps 显式 unknown。
- 输入：`manager.py`、`structured_logging.py`
- 输出：当前 trace_id 过滤、expected steps 更新
- 完成定义（DoD）：
  - 同一 thread 第二轮 structured log 不包含第一轮 middleware steps
  - manager 不伪造 ok，只对缺失 steps 输出 `status=unknown`
  - channel manager 相关测试通过

## Phase 7：文档与验证

- 状态：待开始
- 目标：更新 request-flow 文档并跑快速验证。
- 输入：`docs/request-flow.md`
- 输出：文档、测试结果
- 完成定义（DoD）：
  - 文档说明 `[ManagerStructured]` 和 `[MemoryStructured]` 的关系
  - 文档给出 grep 示例
  - 快速 pytest 命令通过
  - `git diff --check` 通过


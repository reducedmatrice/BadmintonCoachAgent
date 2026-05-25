# Developer Specification (DEV_SPEC)

> 版本：4.3 — Middleware Observability Trace

## 1. 项目概述

### 1.1 项目定位

4.2 已经把一次 channel 请求串成 `channel -> manager -> middleware -> router -> renderer -> outbound` 的统一 request trace。当前问题是 trace 仍偏“业务摘要”，middleware 只显式暴露了 `middleware.multimodal` 和 `middleware.coach_intake`，无法直观看到 coach runtime 实际装配了哪些 middleware、每一层是否运行、是否跳过、是否改写 state，以及 memory queue / memory writeback 到底发生了什么。

本阶段目标是在 4.2 基础上扩展 middleware 可观测性，让一次请求能看到更完整的 runtime 中间过程，特别是：

- middleware 实际装配顺序
- thread data / uploads / sandbox / tool safety / clarification / title / memory / image / loop detection 等层的运行结果
- memory enqueue 的过滤结果、队列状态、消息摘要
- memory 异步写回的 entry、signals、index 更新和保存结果

这不是重写 Agent 控制流，也不是引入外部 tracing 平台；它是在现有 request trace 和 structured logs 上补齐关键 checkpoint。

### 1.2 用户目标

调试时可以从日志里回答：

- 这次请求实际挂了哪些 middleware，顺序是什么？
- 哪些 middleware 执行了，哪些因为条件不满足跳过了？
- Uploads 是否注入了文件块，历史文件和本轮文件各是多少？
- Coach clarification 是否短路模型？
- MemoryMiddleware 是否把本轮对话加入 memory queue？
- 加入 memory queue 前留下了哪些 user / assistant 消息摘要？
- 异步 memory updater 后来有没有真正写入 memory entry 和 memory index？
- 新增了哪些 memory sections / facts / extracted signals？

### 1.3 范围边界

#### 必须完成

- 扩展 request trace helper，支持更具体的 debug summary，同时继续过滤 credentials 类 key。
- 记录 coach runtime middleware registry：`middleware.registry` step，包含实际启用 middleware 名称、顺序和条件性 middleware 是否存在。
- 为基础 middleware 增加 checkpoint：
  - `middleware.thread_data`
  - `middleware.uploads`
  - `middleware.sandbox`
  - `middleware.dangling_tool_call`
  - `middleware.tool_error_handling`
  - `middleware.coach_clarification`
  - `middleware.title`
  - `middleware.memory`
  - `middleware.view_image`
  - `middleware.deferred_tool_filter`
  - `middleware.loop_detection`
  - `middleware.clarification`
- 修复同一 thread 历史 `request_trace.steps` 混入新请求的问题。最终 structured log 只展示当前 `trace_id` 的 steps。
- `middleware.memory` step 必须包含：
  - memory 是否启用
  - skip / queued / error 状态
  - thread_id 是否存在
  - raw message count、filtered message count
  - user / assistant message count
  - enqueue 前队列长度、enqueue 后队列长度
  - filtered user / assistant 摘要，允许包含业务内容 preview
  - agent_name
- 新增异步 memory writeback structured event，例如 `[MemoryStructured] {...}`，记录 queue debounce 后的真实写入结果。
- memory writeback event 必须包含：
  - thread_id / agent_name
  - queued_at / processed_at 或 latency_ms
  - success / skipped / error
  - message_count
  - entry_id / entry_path
  - memory_file path
  - updated_sections
  - new_facts preview
  - facts_removed
  - extracted_signals
  - error_type / reason
- 更新测试，覆盖 helper、middleware registry、memory enqueue trace、memory writeback event。
- 更新 `docs/request-flow.md`，说明 4.3 middleware observability 的读取方式。

#### 不做

- 不做前端 trace viewer。
- 不引入 OpenTelemetry / LangSmith 之类外部平台。
- 不改变 coach router、renderer、intent、memory 的业务语义。
- 不把完整 env、token、API key、Authorization、password、credential 写入日志。
- 不把完整图片 base64、完整附件内容写入日志。
- 不等待异步 memory updater 完成后再回复用户。

### 1.4 隐私和调试内容边界

用户明确希望“中间稍微具体一些，可以有敏感内容，因为要看结果，特别是记忆增加部分”。本阶段采用折中策略：

- 允许 trace 和 memory structured event 记录业务内容 preview，例如用户原句片段、assistant 回复片段、memory fact 内容、memory section summary 的短 preview。
- 允许记录本地 runtime 文件路径，例如 memory entry path、memory index path、review log path、profile path。
- 继续禁止记录 credentials 类内容，包括 key 名中包含 `api_key`、`token`、`secret`、`password`、`authorization`、`credential` 的值。
- 继续禁止记录完整图片 base64、完整上传文件正文、完整 prompt、完整模型回复。

默认文本 preview 上限从 4.2 的 120 字符提升到适合调试的 500 字符；长文本保留 `{length, preview}` 结构。

## 2. 架构设计

### 2.1 Request Trace 当前请求作用域

4.2 的 `ThreadState.request_trace` 使用 reducer 合并 state，但 LangGraph thread 会跨 turn 保留 state，导致旧 middleware step 混入新请求。本期修正为：

- `merge_request_traces(existing, new)` 只合并相同 `trace_id` 的 steps。
- 如果 `new.trace_id != existing.trace_id`，以新的 trace 为准，不继承旧 steps。
- `ChannelManager` 最终输出 structured log 前再次按本轮 `request_trace_id` 规范化。

这样同一 thread 多轮聊天时，structured log 只显示本轮请求的 trace。

### 2.2 Middleware Registry

在 `backend/packages/harness/deerflow/agents/coach_agent/agent.py` 的 `_build_coach_middlewares()` 末尾，根据实际 `middlewares` 追加一个 registry middleware 或直接把 registry 信息注入 runtime metadata。

推荐实现：新增 `TraceRegistryMiddleware`，放在 middleware 链最前或最靠近前面的位置，`before_agent` 追加：

```json
{
  "name": "middleware.registry",
  "layer": "middleware",
  "status": "ok",
  "summary": {
    "runtime": "coach",
    "middleware_order": [
      "TraceRegistryMiddleware",
      "ThreadDataMiddleware",
      "UploadsMiddleware"
    ],
    "count": 14,
    "conditional": {
      "summarization": false,
      "view_image": true,
      "deferred_tool_filter": false
    }
  }
}
```

`TraceRegistryMiddleware` 不改变业务 state，只追加 trace。

### 2.3 Middleware Checkpoint 策略

每个 middleware checkpoint 只记录自己负责的状态，不展开大对象。

| Step | Hook | Status 规则 | Summary |
| ---- | ---- | ---- | ---- |
| `middleware.thread_data` | `before_agent` | `ok/error` | lazy_init、workspace/uploads/outputs path、created/eager |
| `middleware.uploads` | `before_agent` | `ok/skipped` | new_files、historical_files、filenames、extensions、injected_block |
| `middleware.sandbox` | `before_agent/after_agent` | `ok/skipped/error` | lazy_init、acquired、released、sandbox_id 是否存在 |
| `middleware.dangling_tool_call` | `wrap_model_call` | `ok/skipped` | patched_count、missing_tool_call_ids |
| `middleware.tool_error_handling` | `wrap_tool_call` | `ok/error` | tool_name、tool_call_id、error_type |
| `middleware.coach_clarification` | `wrap_model_call` | `ok/skipped` | short_circuited、question preview、missing_slots |
| `middleware.title` | `aafter_model` | `ok/skipped/error` | generated、title preview、reason |
| `middleware.memory` | `after_agent` | `queued/skipped/error` | message counts、queue size、filtered previews |
| `middleware.view_image` | `before_model` | `ok/skipped` | injected、viewed_image_count、tool_call_count |
| `middleware.deferred_tool_filter` | `wrap_model_call` | `ok/skipped` | original_tool_count、filtered_tool_count |
| `middleware.loop_detection` | `after_model` | `ok/warn/error` | tool_names、repeat_count、warning_injected、hard_stop |
| `middleware.clarification` | `wrap_tool_call` | `ok/skipped` | intercepted、question preview、options_count |

对不容易拿到完整内部细节的 middleware，先记录 `skipped` 或粗粒度 count，不为了可观测性重写大量业务代码。

### 2.4 Memory Enqueue Trace

`MemoryMiddleware.after_agent()` 是同步请求链路的一部分，必须进入本轮 `request_trace`：

```json
{
  "name": "middleware.memory",
  "layer": "middleware",
  "status": "queued",
  "summary": {
    "enabled": true,
    "agent_name": "badminton-coach",
    "raw_message_count": 42,
    "filtered_message_count": 8,
    "user_message_count": 4,
    "assistant_message_count": 4,
    "queue_pending_before": 0,
    "queue_pending_after": 1,
    "filtered_user_previews": ["明天打球，休闲打"],
    "filtered_assistant_previews": ["明天休闲打就别把目标定太满..."]
  }
}
```

如果跳过，也必须说明 reason：

- `memory_disabled`
- `missing_thread_id`
- `no_messages`
- `no_user_or_assistant_messages`
- `queue_add_error`

### 2.5 Memory Writeback Event

真正的 memory 更新在 `MemoryUpdateQueue._process_queue()` 后台线程执行，已经不在用户请求生命周期内。它不能可靠塞进已经输出的 `[ManagerStructured]`，因此新增独立结构化日志：

```text
[MemoryStructured] {"event":"memory_update_completed", ...}
```

推荐新增 helper：`deerflow.agents.memory.observability`。

事件示例：

```json
{
  "event": "memory_update_completed",
  "thread_id": "4dcdf...",
  "agent_name": "badminton-coach",
  "success": true,
  "status": "updated",
  "latency_ms": 4210.3,
  "message_count": 8,
  "entry": {
    "entry_id": "mem_20260526_...",
    "entry_path": "/home/ubuntu/data/deer-flow/agents/badminton-coach/memory/2026-05-26.md"
  },
  "memory_file": "/home/ubuntu/data/deer-flow/agents/badminton-coach/memory.json",
  "updates": {
    "updated_sections": ["user.topOfMind"],
    "new_facts": [
      {"category": "badminton", "content": "最近准备多打球", "confidence": 0.8}
    ],
    "facts_removed": [],
    "extracted_signals": ["user.topOfMind", "fact:badminton:最近准备多打球"]
  }
}
```

`MemoryUpdater.update_memory()` 目前只返回 bool。本期把内部结果抽成 `MemoryUpdateResult` dataclass，同时保留 `update_memory()` 对外 bool 兼容，新增 `update_memory_with_result()` 供 queue 使用。

### 2.6 Structured Log 读取方式

调试时有两条日志：

- `[ManagerStructured]`：本次请求同步 trace，包含 middleware registry、各 middleware checkpoint、router、renderer、outbound。
- `[MemoryStructured]`：异步 memory queue 处理结果，按 thread_id / agent_name 关联，通常晚于 ManagerStructured。

远程日志脚本可以继续 grep：

```bash
./scripts/tail-remote-gateway-logs.sh note-agent-server grep -iE "ManagerStructured|MemoryStructured|middleware.memory"
```

## 3. 文件设计

### 3.1 新增文件

- `backend/packages/harness/deerflow/agents/middlewares/request_trace_middleware.py`
  - 放置 `TraceRegistryMiddleware`
  - 放置共享 trace helper，如 `trace_from_state_runtime()`
  - 避免每个 middleware 重复写 `runtime.context["request_trace_id"]`

- `backend/packages/harness/deerflow/agents/memory/observability.py`
  - `MemoryUpdateResult`
  - `build_memory_update_event()`
  - `log_memory_update_event()`
  - preview / diff summary helpers

- `backend/tests/test_middleware_observability_trace.py`
  - 覆盖 registry、thread/uploads/sandbox/memory 等 middleware trace 行为

- `backend/tests/test_memory_observability.py`
  - 覆盖 memory update result 和 structured event

### 3.2 修改文件

- `backend/packages/harness/deerflow/domain/coach/request_trace.py`
  - preview limit 提升
  - 增加按 trace_id reset / filter 的 merge 行为
  - 保留 credentials key 过滤

- `backend/packages/harness/deerflow/agents/thread_state.py`
  - reducer 使用新 merge 语义

- `backend/packages/harness/deerflow/agents/coach_agent/agent.py`
  - 注入 `TraceRegistryMiddleware`
  - registry summary 反映实际 middleware list

- `backend/packages/harness/deerflow/agents/middlewares/*.py`
  - 对核心 middleware 加 request_trace step

- `backend/packages/harness/deerflow/agents/memory/queue.py`
  - 使用 `update_memory_with_result()`
  - 输出 `[MemoryStructured]`

- `backend/packages/harness/deerflow/agents/memory/updater.py`
  - 返回详细 result，同时保持 bool API 兼容

- `backend/app/channels/manager.py`
  - 最终 structured log 前保证只保留当前 request_trace_id steps
  - `_ensure_request_trace_steps()` 增加新 expected steps，但不假装业务已运行；缺失时 `status=unknown`

- `backend/app/channels/structured_logging.py`
  - 确保 request_trace 使用新 normalize 逻辑

- `docs/request-flow.md`
  - 补充 4.3 trace / memory structured event 说明

## 4. 测试方案

### 4.1 单元测试

- `test_request_trace.py`
  - 新 trace_id 替换旧 trace_id 时不会继承旧 steps
  - 普通业务文本 preview 可到 500 字符
  - credentials key 仍被过滤

- `test_coach_agent_entrypoint.py`
  - middleware list 包含 `TraceRegistryMiddleware`
  - registry middleware 位置在链路前段

- `test_middleware_observability_trace.py`
  - ThreadDataMiddleware 追加 `middleware.thread_data`
  - UploadsMiddleware 有文件时追加 `middleware.uploads`
  - MemoryMiddleware queued / skipped 都追加 `middleware.memory`
  - CoachClarificationMiddleware 短路时追加 `middleware.coach_clarification`

- `test_memory_observability.py`
  - MemoryUpdater result 包含 entry metadata、updated sections、new fact preview
  - Memory queue 处理成功/失败时输出 `[MemoryStructured]`

### 4.2 集成回归

运行最快相关集：

```bash
cd backend && uv run pytest \
  tests/test_request_trace.py \
  tests/test_middleware_observability_trace.py \
  tests/test_memory_observability.py \
  tests/test_coach_agent_entrypoint.py \
  tests/test_coach_intake_middleware.py \
  tests/test_structured_logs.py \
  tests/test_channels.py::TestChannelManager::test_handle_chat_creates_thread \
  -q
```

如改动触及 memory updater，补跑：

```bash
cd backend && uv run pytest tests/test_memory_schema.py -q
```

### 4.3 线上验证

部署后发送两类消息：

1. 普通文本：确认 `[ManagerStructured].request_trace.steps` 中出现 registry、thread_data、uploads/skipped、memory queued、outbound。
2. 能触发记忆更新的文本：等待 debounce 后 grep `[MemoryStructured]`，确认 entry_id、updated_sections 或 new_facts 可见。

## 5. 成功标准

- 一次飞书文本请求的 `[ManagerStructured]` 能看到实际 middleware 顺序和主要 middleware checkpoint。
- 同一 thread 连续多轮请求不会混入旧 trace step。
- `middleware.memory` 能显示本轮是否进入 memory queue，以及过滤后消息摘要。
- debounce 后能从 `[MemoryStructured]` 看见 memory 是否真的更新、写到哪个 entry、增加了哪些 signals/facts/sections。
- 日志中没有 credentials 类字段值、完整 base64、完整附件正文。
- 相关测试通过，旧 structured log 字段保持兼容。


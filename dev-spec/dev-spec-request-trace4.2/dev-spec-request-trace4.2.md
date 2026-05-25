# Developer Specification (DEV_SPEC)

> 版本：4.2 — 统一 Request Trace

## 目录

- 项目概述
- 核心特点
- 技术选型
- 测试方案
- 系统架构与模块设计
- 项目排期
- 可扩展性与未来展望

***

## 1. 项目概述

### 1.1 项目定位

本阶段目标是在现有 structured logs 基础上，增加一条统一的 request trace，让一次用户请求经过的关键中间步骤可以被顺序查看。

当前请求链路已经具备合理的上下文层次：

- `run_context`
- `ThreadState`
- `uploaded_files`
- memory index / memory context
- `coach_profile`
- review logs / recall context
- multimodal extraction
- coach router
- response renderer
- channel outbound

但这些信息分散在不同 state 字段、middleware、domain payload 和 manager 汇总日志里。排查问题时，维护者需要在多处日志和结果对象之间来回跳转，不能直观看到“这次请求每一步做了什么、用了哪些上下文、产出了什么决策”。

本阶段新增的 request trace 不替代现有日志，不改变业务语义，而是在请求生命周期内追加阶段级摘要，并在最终 `[ManagerStructured]` 日志里统一输出。

### 1.2 项目目标

**工程目标**

- 为每次 channel chat 请求生成稳定 `trace_id`
- 串联 `channel -> manager -> middleware -> router -> renderer -> outbound`
- 在 trace steps 中记录关键上下文装配、路由决策、渲染结果和出站状态
- 将 trace 嵌入现有 structured log，保持旧 analytics 字段兼容

**调试目标**

- 能看到 run context 最终合并结果
- 能看到上传文件是否被 materialize，以及进入 `uploaded_files` 后是否被多模态处理
- 能看到 `CoachIntakeMiddleware` 识别出的 intent、persona、recall、clarification
- 能看到 router 实际 route、payload 摘要、持久化写回状态
- 能看到 renderer 产出的 response 长度和使用的 recall 表达
- 能看到 outbound 是否为流式、最终文本长度、artifact/attachment 数量

**面试与复盘目标**

- 能把“可观测性”讲成一条贯穿请求生命周期的 trace，而不是零散字段
- 能展示 Agent 系统如何在多层上下文之间保持可解释性
- 能说明每个 trace step 的隐私边界和降级策略

### 1.3 目标用户与使用场景

| 场景 | 输入 | 输出 |
| ---- | ---- | ---- |
| 飞书请求排障 | 一行 `[ManagerStructured]` 日志 | 查看完整 request trace steps |
| 路由误判复盘 | 用户原始请求和最终回复 | 定位 intent、clarification、router、renderer 哪一步偏了 |
| 图片链路排障 | 用户发图后无预期引用 | 查看 materialize、uploads、multimodal extraction、writeback 状态 |
| 记忆引用排障 | 用户期待系统记得历史状态 | 查看 memory/profile/review/recall 是否命中 |
| 面试表达 | “你怎么调试 Agent 中间过程？” | 展示阶段级 trace schema 和结构化日志样例 |

### 1.4 MVP 范围

#### 1.4.1 本期必须完成

- 新增 request trace 数据结构与 helper
- `ThreadState` 支持 `request_trace`
- ChannelManager 创建/传递 `trace_id`
- structured log 增加 `request_trace` 字段
- 至少覆盖以下 steps：
  - `channel.inbound`
  - `manager.thread`
  - `manager.run_context`
  - `manager.upload_materialize`
  - `middleware.multimodal`
  - `middleware.coach_intake`
  - `router.coach_route`
  - `renderer.coach_response`
  - `manager.outbound`
- 单元测试覆盖 trace schema、structured log 提取、middleware/router/renderer 追加 step

#### 1.4.2 本期建议完成

- 为流式 Feishu 增加 `manager.stream_update` 计数摘要
- 在 error 分支中输出 `manager.error` step
- 对 text 字段做长度限制，避免日志过大

#### 1.4.3 本期不纳入 MVP

- 不新增外部可观测平台
- 不重构 analytics 数据库 schema
- 不做前端 trace viewer
- 不记录完整用户原文、完整模型回复或完整文件内容
- 不改变 coach router、renderer、multimodal 的业务行为

### 1.5 当前已知约束

- `ChannelManager` 位于 App 层，不能反向依赖 App 外的 gateway router。
- Harness 层可以被 App 层 import，现有依赖方向是 `app -> deerflow`。
- `ThreadState` 是 LangGraph state schema，新增字段必须可序列化。
- Streaming 路径最终 result 主要来自 `values` 事件；若没有 values，需要基于 latest text 构造降级 result。
- 现有 analytics 解析 `[ManagerStructured]` JSON，新增字段必须向后兼容。
- 日志不能泄露 secrets、env、完整附件内容或大段用户隐私。

### 1.6 关键假设

- 假设 A1：现阶段把 trace 放入 structured log 已能满足“看每个中间步骤”的调试需求。
- 假设 A2：trace step 以摘要为主，不追求记录完整中间对象。
- 假设 A3：App 层 manager step 和 Harness 层 state step 可以通过同一个 `trace_id` 关联。
- 假设 A4：router / renderer 属于 coach domain helper，可以直接追加 trace step 到 payload 或可选 trace 参数。
- 假设 A5：缺失某个阶段信息时，trace 使用 `status=skipped|unknown|error` 显式表达，而不是沉默。

### 1.7 成功标准

- 一次正常 IM chat 请求的 structured log 中包含 `request_trace.trace_id`
- `request_trace.steps` 按执行顺序包含 channel、manager、middleware、router、renderer、outbound
- 每个 step 至少包含 `name / layer / status / timestamp_ms / summary`
- trace 不记录完整 secrets、env 值、完整文件内容
- 旧 structured log 测试继续通过
- 新增 trace 测试覆盖成功、跳过、错误或降级分支

***

## 2. 核心特点

### 2.1 统一 trace，而不是继续堆零散日志

现有 structured logs 已经能回答 route、token、fallback、multimodal 等汇总问题。本阶段补的是顺序化过程视图，让维护者按步骤看一次请求的生命周期。

### 2.2 摘要优先，隐私优先

Trace step 只记录可调试摘要，例如：

- text length
- file count / image count
- route name
- intent source / confidence
- recall 是否命中
- writeback 是否发生
- response length

不记录完整 `.env`、token、私钥、完整图片内容或大段用户原文。

### 2.3 向后兼容现有 analytics

`request_trace` 是 structured log 的新增顶层字段。旧字段如 `event / channel / route / latency_ms / token_usage / multimodal` 保持不变。

### 2.4 App 与 Harness 共享最小 helper

新增 helper 放在 `deerflow.domain.coach.request_trace`，因为当前需求面向 coach trace，且 App 层已经允许 import Harness 层。这样能避免在 App 与 Harness 各自定义一套不一致 schema。

### 2.5 可降级、可局部缺失

如果某个阶段没有运行，trace 仍可输出：

- `status=skipped`
- `summary.reason`

如果某个阶段出错，trace 追加：

- `status=error`
- `summary.error_type`

***

## 3. 技术选型

### 3.1 Trace 数据结构

使用普通 dict/list，而不是 Pydantic 模型。

理由：

- LangGraph state 需要简单可序列化对象
- 现有 structured log helper 也是 dict 风格
- 小 diff，低侵入

最小 schema：

```json
{
  "trace_id": "rt_abc123",
  "steps": [
    {
      "name": "middleware.coach_intake",
      "layer": "middleware",
      "status": "ok",
      "timestamp_ms": 123456789,
      "summary": {
        "primary_intent": "prematch",
        "confidence": 0.82
      }
    }
  ]
}
```

### 3.2 Trace ID 生成

ChannelManager 为 channel chat 请求生成 `trace_id`，并放入 `run_context`：

```python
run_context["request_trace_id"] = trace_id
```

Harness middleware 从 `runtime.context["request_trace_id"]` 读取。同一请求内缺失时使用 helper 生成降级 id。

### 3.3 Trace Step 命名

采用 `<layer>.<action>`：

- `channel.inbound`
- `manager.thread`
- `manager.upload_materialize`
- `manager.run_context`
- `middleware.multimodal`
- `middleware.coach_intake`
- `router.coach_route`
- `renderer.coach_response`
- `manager.outbound`
- `manager.error`

### 3.4 Trace 输出位置

输出位置为 `[ManagerStructured]` JSON 的顶层字段：

```json
{
  "event": "channel_run_completed",
  "request_trace": {
    "trace_id": "rt_...",
    "steps": []
  }
}
```

同时保留 `result["request_trace"]`，方便测试和 LangGraph state 检查。

### 3.5 脱敏与限制

- 字符串默认截断到 200 字符
- list 摘要默认只保留数量或前几个短字符串
- dict 只保留显式 allowlist 字段
- 不记录 `api_key / token / secret / password / authorization` 等 key

***

## 4. 测试方案

### 4.1 设计理念：测试驱动开发 (TDD)

本阶段按 TDD 落地：先写失败测试，再写最小实现。

### 4.2 单元测试

- `backend/tests/test_request_trace.py`
  - trace id 生成格式
  - append step 保序
  - merge trace steps 去重/追加
  - 字符串截断和敏感 key 过滤
- `backend/tests/test_structured_logs.py`
  - `build_run_log_record()` 输出 `request_trace`
  - result 无 trace 时输出降级 trace 或空 steps
- `backend/tests/test_coach_intake_middleware.py`
  - `CoachIntakeMiddleware.before_agent()` 追加 `middleware.coach_intake`
- `backend/tests/test_coach_single_intent_router.py`
  - router payload 追加 `router.coach_route`
  - renderer step 追加 `renderer.coach_response`

### 4.3 集成测试

- 复用 `backend/tests/test_channels.py` 的 fake client / fake bus 模式，验证 non-streaming manager structured log 包含：
  - `channel.inbound`
  - `manager.thread`
  - `manager.run_context`
  - `manager.outbound`

### 4.4 验证命令

优先运行最快相关检查：

```bash
cd backend
uv run pytest tests/test_request_trace.py tests/test_structured_logs.py tests/test_coach_intake_middleware.py tests/test_coach_single_intent_router.py -q
```

如涉及 manager 集成，再补：

```bash
cd backend
uv run pytest tests/test_channels.py -q
```

***

## 5. 系统架构与模块设计

### 5.1 整体架构图

```text
Channel inbound
  -> MessageBus
  -> ChannelManager
     - create trace_id
     - log channel/manager steps
     - pass request_trace_id via run_context
  -> LangGraph / Coach Agent
     - ThreadState.request_trace
     - CoachMultimodalIntakeMiddleware appends multimodal step
     - CoachIntakeMiddleware appends intake step
  -> Coach domain router
     - appends router step to payload/request_trace
  -> Response renderer
     - appends renderer step
  -> ChannelManager
     - extracts result.request_trace
     - appends outbound step
     - writes request_trace into ManagerStructured
  -> Channel outbound
```

### 5.2 目录结构

```text
backend/
  app/channels/
    manager.py
    structured_logging.py
  packages/harness/deerflow/
    agents/
      thread_state.py
      middlewares/
        coach_intake_middleware.py
        coach_multimodal_intake_middleware.py
    domain/coach/
      request_trace.py
      router.py
      response_renderer.py
  tests/
    test_request_trace.py
    test_structured_logs.py
    test_coach_intake_middleware.py
    test_coach_single_intent_router.py
```

### 5.3 模块说明

#### 5.3.1 `request_trace.py`

职责：

- 生成 trace id
- 初始化 trace
- 追加 step
- 合并 trace
- 截断和脱敏 summary

核心函数：

- `new_trace_id() -> str`
- `make_request_trace(trace_id: str | None = None) -> dict`
- `append_trace_step(trace, name, layer, status="ok", summary=None) -> dict`
- `merge_request_traces(existing, new) -> dict`
- `summarize_text(text, limit=120) -> dict`

#### 5.3.2 `ThreadState`

新增：

```python
request_trace: Annotated[dict, merge_request_trace_state]
```

Reducer 使用 request trace helper 合并 steps，避免 middleware 返回局部 step 时覆盖已有 steps。

#### 5.3.3 `ChannelManager`

新增：

- `_start_request_trace(msg)`
- `_trace_step(trace, ...)`
- `_finalize_request_trace(result, trace, ...)`

`_resolve_run_params()` 后把 `request_trace_id` 写入 run context。

#### 5.3.4 Middleware

`CoachMultimodalIntakeMiddleware`：

- 无上传：不追加 step，避免每次请求都产生噪音
- disabled / model_unavailable / skipped / success / extract_failed：追加 `middleware.multimodal`

`CoachIntakeMiddleware`：

- 每次运行追加 `middleware.coach_intake`
- summary 包含 message_count、missing_context、primary_intent、intent_source、confidence、needs_clarification、recall_should_mention、persona_tone

#### 5.3.5 Router 与 Renderer

Router：

- `_run_route_chain()` 在 payload 中追加 `router.coach_route`
- summary 包含 route、intent_source、persisted、writeback flags、recent context degraded flags

Renderer：

- `render_coach_route_payload()` 可选接收 `request_trace`
- 追加 `renderer.coach_response`
- summary 包含 route、response_length、has_recall_line

### 5.4 数据流说明

1. ChannelManager 收到 `InboundMessage`
2. 生成 trace id 和初始 trace
3. trace id 写入 run context
4. LangGraph state 中 middleware 追加 request trace steps
5. router / renderer 把 domain steps 放入 result payload
6. ChannelManager 从 final result 抽取 request trace
7. ChannelManager 追加 outbound step
8. `[ManagerStructured]` 输出完整 trace

### 5.5 错误处理与降级

- manager 异常：追加 `manager.error`，仍发送用户友好错误
- multimodal 异常：记录 `status=error` 和 `error_type`
- result 缺少 request_trace：structured log 输出 manager 侧 trace，不失败
- trace helper 收到非法输入：返回新 trace 或忽略坏 step，不抛业务异常

### 5.6 配置驱动设计

MVP 默认开启 request trace，不新增配置项。

后续如日志体积成为问题，再增加：

- `request_trace_enabled`
- `request_trace_max_steps`
- `request_trace_summary_limit`

***

## 6. 项目排期

### 阶段 A：Spec 与计划

- 目标：明确 request trace schema、接入点、验收标准
- 输出：`dev-spec-request-trace4.2.md`、`tasks.md`、`checklist.md`

### 阶段 B：Trace 基础设施

- 目标：新增 helper、ThreadState reducer、structured log 提取
- 验收：trace helper 与 structured log 测试通过

### 阶段 C：Harness 侧阶段接入

- 目标：middleware/router/renderer 追加步骤
- 验收：coach intake/router/renderer 测试通过

### 阶段 D：Manager 串联与验证

- 目标：ChannelManager 串起 channel/manager/outbound steps
- 验收：相关 channel manager 测试通过，手工查看 structured log JSON 可读

***

## 7. 可扩展性与未来展望

### 7.1 Analytics Trace Viewer

后续可以把 `request_trace.steps` 入库，并在 analytics 页面提供单次请求展开视图。

### 7.2 阶段级耗时

MVP 记录 timestamp，后续可计算 step 间耗时，定位慢点来自 upload、multimodal、router 还是 generation。

### 7.3 与成本拆账合并

可以把 Observability 3.0 的 `router_tokens / memory_context_tokens / generation_tokens` 进一步挂到对应 trace step。

### 7.4 多 channel 统一

当前优先覆盖 IM channel chat。后续可扩展到 Web 前端直接调用 LangGraph 的 path A，让 web 与 IM 拥有一致 trace 视角。

# Middleware Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand request trace so coach runtime middleware and memory enqueue/writeback are observable in logs.

**Architecture:** Keep request trace as serializable dict state. Add a small trace middleware helper for repeated state/runtime plumbing, record current-request middleware steps, and add a separate `[MemoryStructured]` event for asynchronous memory writeback.

**Tech Stack:** Python, LangGraph/LangChain middleware, pytest, existing structured logging conventions.

---

## File Structure

- Modify `backend/packages/harness/deerflow/domain/coach/request_trace.py`: trace merge semantics, preview limit, current-trace filtering helper.
- Create `backend/packages/harness/deerflow/agents/middlewares/request_trace_middleware.py`: shared trace helpers and `TraceRegistryMiddleware`.
- Modify `backend/packages/harness/deerflow/agents/coach_agent/agent.py`: install registry middleware and pass actual middleware names.
- Modify `backend/packages/harness/deerflow/agents/middlewares/memory_middleware.py`: add `middleware.memory` enqueue trace.
- Create `backend/packages/harness/deerflow/agents/memory/observability.py`: memory update result and structured event helpers.
- Modify `backend/packages/harness/deerflow/agents/memory/updater.py`: add detailed result API while preserving bool API.
- Modify `backend/packages/harness/deerflow/agents/memory/queue.py`: log `[MemoryStructured]`.
- Modify selected middleware files for lightweight checkpoints: `thread_data_middleware.py`, `uploads_middleware.py`, `coach_clarification_middleware.py`.
- Modify `backend/app/channels/manager.py` and `backend/app/channels/structured_logging.py`: normalize to current request trace id.
- Add `backend/tests/test_middleware_observability_trace.py`.
- Add `backend/tests/test_memory_observability.py`.
- Update existing tests: `test_request_trace.py`, `test_coach_agent_entrypoint.py`, relevant channel/structured log tests.
- Update `docs/request-flow.md`.

## Task 1: Request Trace Scope And Registry

**Files:**
- Modify: `backend/packages/harness/deerflow/domain/coach/request_trace.py`
- Create: `backend/packages/harness/deerflow/agents/middlewares/request_trace_middleware.py`
- Modify: `backend/packages/harness/deerflow/agents/coach_agent/agent.py`
- Modify: `backend/tests/test_request_trace.py`
- Modify: `backend/tests/test_coach_agent_entrypoint.py`

- [ ] **Step 1: Write failing request trace tests**

Add tests to `backend/tests/test_request_trace.py`:

```python
def test_merge_request_traces_resets_when_new_trace_id_arrives():
    old_trace = append_trace_step(make_request_trace("rt_old"), name="middleware.coach_intake", layer="middleware")
    new_trace = append_trace_step(make_request_trace("rt_new"), name="middleware.memory", layer="middleware")

    merged = merge_request_traces(old_trace, new_trace)

    assert merged["trace_id"] == "rt_new"
    assert [step["name"] for step in merged["steps"]] == ["middleware.memory"]


def test_sanitize_summary_keeps_longer_business_preview_but_filters_credentials():
    summary = sanitize_summary({"text": "球" * 700, "Authorization": "Bearer secret"})

    assert summary["text"]["length"] == 700
    assert len(summary["text"]["preview"]) == 500
    assert "Authorization" not in summary
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_request_trace.py -q
```

Expected: new tests fail because old merge keeps old trace id or preview is 120.

- [ ] **Step 3: Implement trace scope changes**

In `request_trace.py`:

```python
DEFAULT_TEXT_LIMIT = 500

def merge_request_traces(existing: Any, new: Any) -> dict[str, Any]:
    left = normalize_request_trace(existing) if isinstance(existing, Mapping) else {"trace_id": None, "steps": []}
    right = normalize_request_trace(new, fallback_trace_id=left.get("trace_id") if isinstance(left.get("trace_id"), str) else None) if isinstance(new, Mapping) else {"trace_id": None, "steps": []}

    left_trace_id = left.get("trace_id") if isinstance(left.get("trace_id"), str) else None
    right_trace_id = right.get("trace_id") if isinstance(right.get("trace_id"), str) else None

    if right_trace_id and left_trace_id and right_trace_id != left_trace_id:
        left = {"trace_id": right_trace_id, "steps": []}

    trace_id = right_trace_id or left_trace_id or new_trace_id()
    steps = []
    seen = set()
    for candidate in [*(left.get("steps") or []), *(right.get("steps") or [])]:
        if isinstance(candidate, Mapping):
            normalized = _normalize_step(candidate)
            fingerprint = _step_fingerprint(normalized)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            steps.append(normalized)
    return {"trace_id": trace_id, "steps": steps}
```

If exact code needs minor adjustment, preserve the behavior above.

- [ ] **Step 4: Add registry middleware tests**

In `backend/tests/test_coach_agent_entrypoint.py`, add assertions:

```python
def test_build_coach_middlewares_includes_trace_registry_first(monkeypatch):
    app_config = _make_app_config([_make_model("vision-model", supports_thinking=True, supports_vision=True)])
    monkeypatch.setattr(coach_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(coach_agent_module, "_create_summarization_middleware", lambda: None)

    middlewares = coach_agent_module._build_coach_middlewares(
        {"configurable": {"agent_name": "badminton-coach"}},
        model_name="vision-model",
        agent_name="badminton-coach",
    )

    names = [type(m).__name__ for m in middlewares]
    assert names[0] == "TraceRegistryMiddleware"
    registry = middlewares[0]
    assert registry.middleware_order[0] == "TraceRegistryMiddleware"
    assert "MemoryMiddleware" in registry.middleware_order
```

- [ ] **Step 5: Implement `TraceRegistryMiddleware`**

Create `backend/packages/harness/deerflow/agents/middlewares/request_trace_middleware.py`:

```python
from __future__ import annotations

from typing import Any, Mapping, NotRequired, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime

from deerflow.domain.coach.request_trace import append_trace_step, make_request_trace


class RequestTraceMiddlewareState(AgentState):
    request_trace: NotRequired[dict[str, Any] | None]


def get_trace_from_state_runtime(state: Mapping[str, Any], runtime: Runtime) -> dict[str, Any]:
    trace_id = runtime.context.get("request_trace_id") if runtime.context else None
    return state.get("request_trace") or make_request_trace(trace_id if isinstance(trace_id, str) else None)


def append_middleware_trace(
    state: Mapping[str, Any],
    runtime: Runtime,
    *,
    name: str,
    status: str = "ok",
    summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return append_trace_step(
        get_trace_from_state_runtime(state, runtime),
        name=name,
        layer="middleware",
        status=status,
        summary=summary or {},
    )


class TraceRegistryMiddleware(AgentMiddleware[RequestTraceMiddlewareState]):
    state_schema = RequestTraceMiddlewareState

    def __init__(self, middleware_order: list[str], conditional: Mapping[str, bool] | None = None):
        super().__init__()
        self.middleware_order = list(middleware_order)
        self.conditional = dict(conditional or {})

    @override
    def before_agent(self, state: RequestTraceMiddlewareState, runtime: Runtime) -> dict | None:
        trace = append_middleware_trace(
            state,
            runtime,
            name="middleware.registry",
            status="ok",
            summary={
                "runtime": "coach",
                "count": len(self.middleware_order),
                "middleware_order": self.middleware_order,
                "conditional": self.conditional,
            },
        )
        return {"request_trace": trace}
```

- [ ] **Step 6: Install registry middleware**

In `_build_coach_middlewares`, after building the current list, prepend registry:

```python
from deerflow.agents.middlewares.request_trace_middleware import TraceRegistryMiddleware

conditional = {
    "summarization": summarization_middleware is not None,
    "view_image": model_config is not None and model_config.supports_vision,
    "deferred_tool_filter": app_config.tool_search.enabled,
}
names = ["TraceRegistryMiddleware", *[type(m).__name__ for m in middlewares]]
middlewares.insert(0, TraceRegistryMiddleware(names, conditional=conditional))
return middlewares
```

- [ ] **Step 7: Run Task 1 tests**

Run:

```bash
cd backend && uv run pytest tests/test_request_trace.py tests/test_coach_agent_entrypoint.py -q
```

Expected: pass.

## Task 2: Memory Enqueue Trace

**Files:**
- Modify: `backend/packages/harness/deerflow/agents/middlewares/memory_middleware.py`
- Add: `backend/tests/test_middleware_observability_trace.py`

- [ ] **Step 1: Write tests for memory queued and skipped**

Create `backend/tests/test_middleware_observability_trace.py` with tests that monkeypatch memory config and queue:

```python
from __future__ import annotations

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

from deerflow.agents.middlewares.memory_middleware import MemoryMiddleware


class _Runtime:
    def __init__(self, context):
        self.context = context


class _Queue:
    def __init__(self):
        self.pending_count = 0
        self.calls = []

    def add(self, **kwargs):
        self.calls.append(kwargs)
        self.pending_count += 1


def test_memory_middleware_traces_queued_update(monkeypatch):
    queue = _Queue()
    monkeypatch.setattr("deerflow.agents.middlewares.memory_middleware.get_memory_config", lambda: SimpleNamespace(enabled=True))
    monkeypatch.setattr("deerflow.agents.middlewares.memory_middleware.get_memory_queue", lambda: queue)

    result = MemoryMiddleware(agent_name="badminton-coach").after_agent(
        {"messages": [HumanMessage(content="明天打球，休闲打"), AIMessage(content="明天休闲打就别把目标定太满。")]},
        _Runtime({"thread_id": "thread-1", "request_trace_id": "rt_memory"}),
    )

    assert result is not None
    step = result["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.memory"
    assert step["status"] == "queued"
    assert step["summary"]["raw_message_count"] == 2
    assert step["summary"]["filtered_message_count"] == 2
    assert step["summary"]["queue_pending_before"] == 0
    assert step["summary"]["queue_pending_after"] == 1
    assert step["summary"]["filtered_user_previews"] == ["明天打球，休闲打"]


def test_memory_middleware_traces_disabled_skip(monkeypatch):
    monkeypatch.setattr("deerflow.agents.middlewares.memory_middleware.get_memory_config", lambda: SimpleNamespace(enabled=False))

    result = MemoryMiddleware(agent_name="badminton-coach").after_agent(
        {"messages": [HumanMessage(content="hello"), AIMessage(content="hi")]},
        _Runtime({"thread_id": "thread-1", "request_trace_id": "rt_memory"}),
    )

    step = result["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.memory"
    assert step["status"] == "skipped"
    assert step["summary"]["reason"] == "memory_disabled"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend && uv run pytest tests/test_middleware_observability_trace.py -q
```

Expected: fail because `MemoryMiddleware` returns None and no trace.

- [ ] **Step 3: Implement memory trace helpers**

In `memory_middleware.py`, import `append_middleware_trace`. Add small preview helpers:

```python
def _message_preview(message: Any, limit: int = 500) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, list):
        content = " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    text = str(content).strip()
    return text[:limit]


def _trace_memory(state: MemoryMiddlewareState, runtime: Runtime, *, status: str, summary: dict[str, Any]) -> dict:
    return {"request_trace": append_middleware_trace(state, runtime, name="middleware.memory", status=status, summary=summary)}
```

- [ ] **Step 4: Return trace on every memory branch**

Update `after_agent`:

- If disabled, return skipped trace with `reason=memory_disabled`.
- If missing thread id, return skipped trace with `reason=missing_thread_id`.
- If no messages, return skipped trace with `reason=no_messages`.
- If no user or assistant messages after filtering, return skipped trace with counts and `reason=no_user_or_assistant_messages`.
- Around queue add, capture `queue_pending_before` and `queue_pending_after`.
- On queue add success, return queued trace.
- On exception, return error trace with `error_type`.

- [ ] **Step 5: Run Task 2 tests**

Run:

```bash
cd backend && uv run pytest tests/test_middleware_observability_trace.py -q
```

Expected: pass.

## Task 3: Memory Writeback Structured Event

**Files:**
- Create: `backend/packages/harness/deerflow/agents/memory/observability.py`
- Modify: `backend/packages/harness/deerflow/agents/memory/updater.py`
- Modify: `backend/packages/harness/deerflow/agents/memory/queue.py`
- Add: `backend/tests/test_memory_observability.py`

- [ ] **Step 1: Write memory observability tests**

Create `backend/tests/test_memory_observability.py`:

```python
from __future__ import annotations

import json
import logging

from deerflow.agents.memory.observability import MemoryUpdateResult, build_memory_update_event, format_memory_update_event


def test_build_memory_update_event_includes_update_details():
    result = MemoryUpdateResult(
        status="updated",
        success=True,
        thread_id="thread-1",
        agent_name="badminton-coach",
        message_count=2,
        entry_id="mem_1",
        entry_path="/tmp/memory/2026-05-26.md",
        memory_file="/tmp/memory.json",
        updated_sections=["user.topOfMind"],
        new_facts=[{"category": "badminton", "content": "最近准备多打球", "confidence": 0.8}],
        facts_removed=["fact_old"],
        extracted_signals=["user.topOfMind", "fact:badminton:最近准备多打球"],
        latency_ms=12.5,
    )

    event = build_memory_update_event(result)

    assert event["event"] == "memory_update_completed"
    assert event["success"] is True
    assert event["entry"]["entry_id"] == "mem_1"
    assert event["updates"]["updated_sections"] == ["user.topOfMind"]
    assert event["updates"]["new_facts"][0]["content"] == "最近准备多打球"


def test_format_memory_update_event_is_json():
    payload = format_memory_update_event(MemoryUpdateResult(status="skipped", success=False, reason="memory_disabled"))

    parsed = json.loads(payload)
    assert parsed["event"] == "memory_update_completed"
    assert parsed["status"] == "skipped"
    assert parsed["reason"] == "memory_disabled"
```

- [ ] **Step 2: Implement observability dataclass and event formatter**

Create `observability.py`:

```python
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from deerflow.domain.coach.request_trace import sanitize_summary

logger = logging.getLogger(__name__)


@dataclass
class MemoryUpdateResult:
    status: str
    success: bool
    thread_id: str | None = None
    agent_name: str | None = None
    message_count: int = 0
    entry_id: str = ""
    entry_path: str = ""
    memory_file: str = ""
    updated_sections: list[str] = field(default_factory=list)
    new_facts: list[dict[str, Any]] = field(default_factory=list)
    facts_removed: list[str] = field(default_factory=list)
    extracted_signals: list[str] = field(default_factory=list)
    latency_ms: float | None = None
    reason: str = ""
    error_type: str = ""


def build_memory_update_event(result: MemoryUpdateResult) -> dict[str, Any]:
    return sanitize_summary(
        {
            "event": "memory_update_completed",
            "thread_id": result.thread_id or "",
            "agent_name": result.agent_name or "",
            "success": result.success,
            "status": result.status,
            "latency_ms": result.latency_ms,
            "message_count": result.message_count,
            "entry": {"entry_id": result.entry_id, "entry_path": result.entry_path},
            "memory_file": result.memory_file,
            "updates": {
                "updated_sections": result.updated_sections,
                "new_facts": result.new_facts,
                "facts_removed": result.facts_removed,
                "extracted_signals": result.extracted_signals,
            },
            "reason": result.reason,
            "error_type": result.error_type,
        }
    )


def format_memory_update_event(result: MemoryUpdateResult) -> str:
    return json.dumps(build_memory_update_event(result), ensure_ascii=False, sort_keys=True)


def log_memory_update_event(result: MemoryUpdateResult) -> None:
    logger.info("[MemoryStructured] %s", format_memory_update_event(result))
```

- [ ] **Step 3: Add detailed updater API**

In `updater.py`, add `update_memory_with_result()` that contains the existing logic and returns `MemoryUpdateResult`. Keep `update_memory()`:

```python
def update_memory(self, messages: list[Any], thread_id: str | None = None, agent_name: str | None = None) -> bool:
    return self.update_memory_with_result(messages, thread_id, agent_name).success
```

In the detailed method:

- Return `MemoryUpdateResult(status="skipped", success=False, reason="memory_disabled")` for disabled config.
- Return skipped for no messages / empty conversation / missing thread_id / entry append failure.
- On success, include entry metadata, memory file path, updated sections, new facts, facts removed, extracted signals, latency.
- On JSON error or exception, include `status="error"` and `error_type`.

Use helper functions:

```python
def _extract_updated_sections(update_data: dict[str, Any]) -> list[str]:
    sections: list[str] = []
    for group_name in ("user", "history"):
        group = update_data.get(group_name, {})
        if not isinstance(group, dict):
            continue
        for section_name, payload in group.items():
            if isinstance(payload, dict) and payload.get("shouldUpdate") and payload.get("summary"):
                sections.append(f"{group_name}.{section_name}")
    return sections

def _extract_new_fact_summaries(update_data: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for fact in update_data.get("newFacts", []):
        if not isinstance(fact, dict):
            continue
        facts.append(
            {
                "category": str(fact.get("category") or "context"),
                "content": str(fact.get("content") or "")[:500],
                "confidence": fact.get("confidence", 0.5),
            }
        )
    return facts
```

- [ ] **Step 4: Log result from queue**

In `queue.py`, call:

```python
result = updater.update_memory_with_result(...)
log_memory_update_event(result)
success = result.success
```

Keep existing print messages if useful, but structured event is the authoritative new signal.

- [ ] **Step 5: Run memory observability tests**

Run:

```bash
cd backend && uv run pytest tests/test_memory_observability.py tests/test_memory_schema.py -q
```

Expected: pass.

## Task 4: Representative Middleware Checkpoints

**Files:**
- Modify: `thread_data_middleware.py`
- Modify: `uploads_middleware.py`
- Modify: `coach_clarification_middleware.py`
- Extend: `backend/tests/test_middleware_observability_trace.py`

- [ ] **Step 1: Add tests for representative checkpoints**

Add tests for:

- `ThreadDataMiddleware.before_agent()` returns `request_trace` with `middleware.thread_data`.
- `UploadsMiddleware.before_agent()` with one uploaded file returns `request_trace` with `middleware.uploads`.
- `CoachClarificationMiddleware.wrap_model_call()` short-circuit returns AIMessage and mutates request state with `middleware.coach_clarification` if possible; if mutation is awkward, document and trace skipped path through registry.

- [ ] **Step 2: Implement thread_data trace**

In `ThreadDataMiddleware.before_agent()`, include `request_trace` in return:

```python
trace = append_middleware_trace(
    state,
    runtime,
    name="middleware.thread_data",
    status="ok",
    summary={"lazy_init": self._lazy_init, "created": not self._lazy_init, **paths},
)
return {"thread_data": {**paths}, "request_trace": trace}
```

- [ ] **Step 3: Implement uploads trace**

In `UploadsMiddleware.before_agent()`, trace skipped no messages/non-human/no files and ok injection. For no files, return a trace-only state update:

```python
trace = append_middleware_trace(
    state,
    runtime,
    name="middleware.uploads",
    status="skipped",
    summary={"reason": "no_uploaded_files", "new_file_count": 0, "historical_file_count": 0},
)
return {"request_trace": trace}
```

For injected files, include counts, filenames, extensions, and `injected_block=True`.

- [ ] **Step 4: Implement coach clarification trace**

Because `wrap_model_call` returns a model result rather than state update, prefer a non-invasive approach:

- In `_build_clarification_message`, when clarification exists, mutate `request.state["request_trace"]` with `middleware.coach_clarification`.
- For no clarification, do not add a step on every model call to avoid noisy repeated steps; registry proves middleware exists.

- [ ] **Step 5: Run representative tests**

Run:

```bash
cd backend && uv run pytest tests/test_middleware_observability_trace.py tests/test_coach_clarification_middleware.py tests/test_uploads_middleware_core_logic.py -q
```

Expected: pass.

## Task 5: Manager, Docs, And Final Verification

**Files:**
- Modify: `backend/app/channels/manager.py`
- Modify: `backend/app/channels/structured_logging.py`
- Modify: `docs/request-flow.md`
- Modify: `dev-spec/dev-spec-middleware-observability4.3/checklist.md`

- [ ] **Step 1: Ensure current trace id in manager output**

Before injecting/logging request trace, normalize to the current `request_trace["trace_id"]`. If needed, add helper in `request_trace.py`:

```python
def filter_trace_steps_by_trace_id(trace: Any, trace_id: str) -> dict[str, Any]:
    normalized = normalize_request_trace(trace, fallback_trace_id=trace_id)
    if normalized["trace_id"] != trace_id:
        return make_request_trace(trace_id)
    return normalized
```

- [ ] **Step 2: Update expected steps list**

In `manager.py`, include new major steps in `_ensure_request_trace_steps()`:

```python
("middleware.registry", "middleware"),
("middleware.thread_data", "middleware"),
("middleware.uploads", "middleware"),
("middleware.memory", "middleware"),
```

Do not mark missing steps as ok. Keep `status="unknown"`.

- [ ] **Step 3: Update request-flow docs**

Add a section explaining:

- `[ManagerStructured].request_trace` is synchronous request trace.
- `[MemoryStructured]` is asynchronous memory writeback result.
- Example grep command.
- Credentials/base64/attachment content are still excluded.

- [ ] **Step 4: Update checklist**

Mark completed checklist items in `dev-spec/dev-spec-middleware-observability4.3/checklist.md` only after implementation and tests pass.

- [ ] **Step 5: Run final verification**

Run:

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

Then:

```bash
git diff --check
```

Expected: tests and diff check pass.

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NotRequired, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime

from deerflow.domain.coach.request_trace import append_trace_step, filter_trace_steps_by_trace_id, make_request_trace


class RequestTraceMiddlewareState(AgentState):
    request_trace: NotRequired[dict[str, Any] | None]


def get_trace_from_state_runtime(state: Mapping[str, Any], runtime: Runtime) -> dict[str, Any]:
    context = runtime.context or {}
    trace_id = context.get("request_trace_id")
    if isinstance(trace_id, str) and trace_id:
        return filter_trace_steps_by_trace_id(state.get("request_trace"), trace_id)
    return state.get("request_trace") or make_request_trace(None)


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

"""Coach-specific clarification short-circuit middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Mapping, override
from uuid import uuid4

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage


class CoachClarificationMiddlewareState(AgentState):
    """State compatible with coach intake payload."""

    coach_intake: dict[str, Any] | None


class CoachClarificationMiddleware(AgentMiddleware[CoachClarificationMiddlewareState]):
    """Short-circuit model execution when coach intake already decided to clarify."""

    state_schema = CoachClarificationMiddlewareState

    def _build_clarification_message(self, request: ModelRequest) -> AIMessage | None:
        state = request.state
        coach_intake = state.get("coach_intake") if isinstance(state, Mapping) else None
        if not isinstance(coach_intake, Mapping):
            return None

        clarification_request = coach_intake.get("clarification_request")
        if not isinstance(clarification_request, Mapping):
            return None

        question = clarification_request.get("question")
        if not isinstance(question, str) or not question.strip():
            return None

        tool_call_id = f"coach_clarification_{uuid4().hex}"
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "id": tool_call_id,
                    "name": "ask_clarification",
                    "args": dict(clarification_request),
                    "type": "tool_call",
                }
            ],
        )

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        clarification_message = self._build_clarification_message(request)
        if clarification_message is not None:
            return clarification_message
        return handler(request)

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        clarification_message = self._build_clarification_message(request)
        if clarification_message is not None:
            return clarification_message
        return await handler(request)

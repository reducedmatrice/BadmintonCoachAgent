"""Coach intake middleware skeleton.

This middleware normalizes the latest user input and aggregates thread context
into a single structured object for downstream coach runtime layers.
"""

from __future__ import annotations

from typing import Any, NotRequired, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime

from deerflow.agents.thread_state import CoachIntakeData, ThreadDataState
from deerflow.domain.coach import build_clarification_request, default_coach_persona, detect_coach_intent, resolve_coach_persona


class CoachIntakeMiddlewareState(AgentState):
    """Compatible with the `ThreadState` schema."""

    thread_data: NotRequired[ThreadDataState | None]
    coach_intake: NotRequired[CoachIntakeData | None]


def _extract_text(content: Any) -> str | None:
    """Extract readable text from a LangChain content payload."""
    if isinstance(content, str):
        value = content.strip()
        return value or None

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if isinstance(block.get("text"), str):
                    text = block["text"].strip()
                    if text:
                        parts.append(text)
                elif block.get("type") == "text" and isinstance(block.get("content"), str):
                    text = block["content"].strip()
                    if text:
                        parts.append(text)
            elif isinstance(block, str):
                text = block.strip()
                if text:
                    parts.append(text)
        if not parts:
            return None
        return "\n".join(parts)

    return None


class CoachIntakeMiddleware(AgentMiddleware[CoachIntakeMiddlewareState]):
    """Build a structured coach intake payload before agent execution."""

    state_schema = CoachIntakeMiddlewareState

    @override
    def before_agent(self, state: CoachIntakeMiddlewareState, runtime: Runtime) -> dict | None:
        messages = state.get("messages", [])
        latest_user_input: str | None = None

        for msg in reversed(messages):
            if getattr(msg, "type", None) == "human":
                latest_user_input = _extract_text(getattr(msg, "content", None))
                break

        thread_id = runtime.context.get("thread_id")
        thread_data = state.get("thread_data")
        missing_context: list[str] = []
        if thread_id is None:
            missing_context.append("thread_id")
        if not thread_data:
            missing_context.append("thread_data")

        persona, ignored_overrides = resolve_coach_persona(default_coach_persona(), runtime.context)
        intent = detect_coach_intent(latest_user_input or "")
        clarification_request = build_clarification_request(intent, persona=persona)

        intake: CoachIntakeData = {
            "thread_id": thread_id,
            "latest_user_input": latest_user_input,
            "message_count": len(messages),
            "thread_data": thread_data,
            "missing_context": missing_context,
            # Placeholders for A3/B/C follow-up layers to consume.
            "memory_context": state.get("memory"),
            "coach_profile": state.get("coach_profile"),
            "review_context": [],
            "persona": persona.model_dump(),
            "persona_ignored_overrides": ignored_overrides,
            "intent": {
                "primary_intent": intent.primary_intent,
                "secondary_intents": intent.secondary_intents,
                "slots": intent.slots,
                "missing_slots": intent.missing_slots,
                "risk_level": intent.risk_level,
                "confidence": intent.confidence,
                "source": intent.source,
                "needs_clarification": intent.needs_clarification,
                "clarification_reason": intent.clarification_reason,
            },
            "clarification_request": clarification_request,
        }
        return {"coach_intake": intake}

"""Middleware for memory mechanism."""

import re
from typing import Any, NotRequired, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime

from deerflow.agents.memory.queue import get_memory_queue
from deerflow.agents.middlewares.request_trace_middleware import append_middleware_trace
from deerflow.config.memory_config import get_memory_config


class MemoryMiddlewareState(AgentState):
    """Compatible with the `ThreadState` schema."""

    request_trace: NotRequired[dict[str, Any] | None]


def _filter_messages_for_memory(messages: list[Any]) -> list[Any]:
    """Filter messages to keep only user inputs and final assistant responses.

    This filters out:
    - Tool messages (intermediate tool call results)
    - AI messages with tool_calls (intermediate steps, not final responses)
    - The <uploaded_files> block injected by UploadsMiddleware into human messages
      (file paths are session-scoped and must not persist in long-term memory).
      The user's actual question is preserved; only turns whose content is entirely
      the upload block (nothing remains after stripping) are dropped along with
      their paired assistant response.

    Only keeps:
    - Human messages (with the ephemeral upload block removed)
    - AI messages without tool_calls (final assistant responses), unless the
      paired human turn was upload-only and had no real user text.

    Args:
        messages: List of all conversation messages.

    Returns:
        Filtered list containing only user inputs and final assistant responses.
    """
    _UPLOAD_BLOCK_RE = re.compile(r"<uploaded_files>[\s\S]*?</uploaded_files>\n*", re.IGNORECASE)

    filtered = []
    skip_next_ai = False
    for msg in messages:
        msg_type = getattr(msg, "type", None)

        if msg_type == "human":
            content = getattr(msg, "content", "")
            if isinstance(content, list):
                content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
            content_str = str(content)
            if "<uploaded_files>" in content_str:
                # Strip the ephemeral upload block; keep the user's real question.
                stripped = _UPLOAD_BLOCK_RE.sub("", content_str).strip()
                if not stripped:
                    # Nothing left — the entire turn was upload bookkeeping;
                    # skip it and the paired assistant response.
                    skip_next_ai = True
                    continue
                # Rebuild the message with cleaned content so the user's question
                # is still available for memory summarisation.
                from copy import copy

                clean_msg = copy(msg)
                clean_msg.content = stripped
                filtered.append(clean_msg)
                skip_next_ai = False
            else:
                filtered.append(msg)
                skip_next_ai = False
        elif msg_type == "ai":
            tool_calls = getattr(msg, "tool_calls", None)
            if not tool_calls:
                if skip_next_ai:
                    skip_next_ai = False
                    continue
                filtered.append(msg)
        # Skip tool messages and AI messages with tool_calls

    return filtered


def _message_preview(message: Any, limit: int = 500) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, list):
        content = " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    return str(content).strip()[:limit]


def _queue_pending_count(queue: Any) -> int | None:
    pending_count = getattr(queue, "pending_count", None)
    if isinstance(pending_count, int) and not isinstance(pending_count, bool):
        return pending_count
    return None


def _trace_memory(state: MemoryMiddlewareState, runtime: Runtime, *, status: str, summary: dict[str, Any]) -> dict:
    return {
        "request_trace": append_middleware_trace(
            state,
            runtime,
            name="middleware.memory",
            status=status,
            summary=summary,
        )
    }


class MemoryMiddleware(AgentMiddleware[MemoryMiddlewareState]):
    """Middleware that queues conversation for memory update after agent execution.

    This middleware:
    1. After each agent execution, queues the conversation for memory update
    2. Only includes user inputs and final assistant responses (ignores tool calls)
    3. The queue uses debouncing to batch multiple updates together
    4. Memory is updated asynchronously via LLM summarization
    """

    state_schema = MemoryMiddlewareState

    def __init__(self, agent_name: str | None = None):
        """Initialize the MemoryMiddleware.

        Args:
            agent_name: If provided, memory is stored per-agent. If None, uses global memory.
        """
        super().__init__()
        self._agent_name = agent_name

    @override
    def after_agent(self, state: MemoryMiddlewareState, runtime: Runtime) -> dict | None:
        """Queue conversation for memory update after agent completes.

        Args:
            state: The current agent state.
            runtime: The runtime context.

        Returns:
            None (no state changes needed from this middleware).
        """
        config = get_memory_config()
        if not config.enabled:
            return _trace_memory(
                state,
                runtime,
                status="skipped",
                summary={"enabled": False, "agent_name": self._agent_name or "", "reason": "memory_disabled"},
            )

        # Get thread ID from runtime context
        context = runtime.context or {}
        thread_id = context.get("thread_id")
        if not thread_id:
            print("MemoryMiddleware: No thread_id in context, skipping memory update")
            return _trace_memory(
                state,
                runtime,
                status="skipped",
                summary={"enabled": True, "agent_name": self._agent_name or "", "reason": "missing_thread_id"},
            )

        # Get messages from state
        messages = state.get("messages", [])
        if not messages:
            print("MemoryMiddleware: No messages in state, skipping memory update")
            return _trace_memory(
                state,
                runtime,
                status="skipped",
                summary={"enabled": True, "agent_name": self._agent_name or "", "reason": "no_messages", "raw_message_count": 0},
            )

        # Filter to only keep user inputs and final assistant responses
        filtered_messages = _filter_messages_for_memory(messages)

        # Only queue if there's meaningful conversation
        # At minimum need one user message and one assistant response
        user_messages = [m for m in filtered_messages if getattr(m, "type", None) == "human"]
        assistant_messages = [m for m in filtered_messages if getattr(m, "type", None) == "ai"]

        if not user_messages or not assistant_messages:
            return _trace_memory(
                state,
                runtime,
                status="skipped",
                summary={
                    "enabled": True,
                    "agent_name": self._agent_name or "",
                    "reason": "no_user_or_assistant_messages",
                    "raw_message_count": len(messages),
                    "filtered_message_count": len(filtered_messages),
                    "user_message_count": len(user_messages),
                    "assistant_message_count": len(assistant_messages),
                    "filtered_user_previews": [_message_preview(message) for message in user_messages],
                    "filtered_assistant_previews": [_message_preview(message) for message in assistant_messages],
                },
            )

        # Queue the filtered conversation for memory update
        try:
            queue = get_memory_queue()
            queue_pending_before = _queue_pending_count(queue)
            queue.add(thread_id=thread_id, messages=filtered_messages, agent_name=self._agent_name)
            queue_pending_after = _queue_pending_count(queue)
        except Exception as exc:
            return _trace_memory(
                state,
                runtime,
                status="error",
                summary={
                    "enabled": True,
                    "agent_name": self._agent_name or "",
                    "error_type": type(exc).__name__,
                    "raw_message_count": len(messages),
                    "filtered_message_count": len(filtered_messages),
                    "user_message_count": len(user_messages),
                    "assistant_message_count": len(assistant_messages),
                },
            )

        return _trace_memory(
            state,
            runtime,
            status="queued",
            summary={
                "enabled": True,
                "agent_name": self._agent_name or "",
                "raw_message_count": len(messages),
                "filtered_message_count": len(filtered_messages),
                "user_message_count": len(user_messages),
                "assistant_message_count": len(assistant_messages),
                "queue_pending_before": queue_pending_before,
                "queue_pending_after": queue_pending_after,
                "filtered_user_previews": [_message_preview(message) for message in user_messages],
                "filtered_assistant_previews": [_message_preview(message) for message in assistant_messages],
            },
        )

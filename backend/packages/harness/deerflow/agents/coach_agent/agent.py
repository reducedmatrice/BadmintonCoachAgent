"""Coach runtime entrypoint and middleware composition."""

from __future__ import annotations

import logging

from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig

from deerflow.agents.lead_agent.agent import _create_summarization_middleware, _resolve_model_name
from deerflow.agents.lead_agent.prompt import apply_prompt_template
from deerflow.agents.middlewares.coach_clarification_middleware import CoachClarificationMiddleware
from deerflow.agents.middlewares.coach_intake_middleware import CoachIntakeMiddleware
from deerflow.agents.middlewares.clarification_middleware import ClarificationMiddleware
from deerflow.agents.middlewares.loop_detection_middleware import LoopDetectionMiddleware
from deerflow.agents.middlewares.memory_middleware import MemoryMiddleware
from deerflow.agents.middlewares.title_middleware import TitleMiddleware
from deerflow.agents.middlewares.tool_error_handling_middleware import build_lead_runtime_middlewares
from deerflow.agents.middlewares.view_image_middleware import ViewImageMiddleware
from deerflow.agents.thread_state import ThreadState
from deerflow.config.agents_config import load_agent_config
from deerflow.config.app_config import get_app_config
from deerflow.models import create_chat_model

logger = logging.getLogger(__name__)


def _build_coach_middlewares(config: RunnableConfig, model_name: str | None, agent_name: str | None = None):
    """Build coach runtime middleware chain.

    A2: Keep base middlewares and remove generic orchestration middlewares.
    Removed: TodoMiddleware, SubagentLimitMiddleware.
    Compatible keep: ClarificationMiddleware.
    """
    middlewares = build_lead_runtime_middlewares(lazy_init=True)
    middlewares.append(CoachIntakeMiddleware())
    middlewares.append(CoachClarificationMiddleware())

    summarization_middleware = _create_summarization_middleware()
    if summarization_middleware is not None:
        middlewares.append(summarization_middleware)

    middlewares.append(TitleMiddleware())
    middlewares.append(MemoryMiddleware(agent_name=agent_name))

    app_config = get_app_config()
    model_config = app_config.get_model_config(model_name) if model_name else None
    if model_config is not None and model_config.supports_vision:
        middlewares.append(ViewImageMiddleware())

    # Keep deferred-tool schema filtering behavior aligned with prompt/tool_search.
    if app_config.tool_search.enabled:
        from deerflow.agents.middlewares.deferred_tool_filter_middleware import DeferredToolFilterMiddleware

        middlewares.append(DeferredToolFilterMiddleware())

    middlewares.append(LoopDetectionMiddleware())
    middlewares.append(ClarificationMiddleware())
    return middlewares


def make_coach_agent(config: RunnableConfig):
    """Create coach runtime agent.

    A2 keeps coach runtime independent from lead runtime entry assembly.
    """
    # Lazy import to avoid circular dependency
    from deerflow.tools import get_available_tools
    from deerflow.tools.builtins import setup_agent

    cfg = config.get("configurable", {})

    thinking_enabled = cfg.get("thinking_enabled", True)
    reasoning_effort = cfg.get("reasoning_effort", None)
    requested_model_name: str | None = cfg.get("model_name") or cfg.get("model")
    max_concurrent_subagents = cfg.get("max_concurrent_subagents", 3)
    is_bootstrap = cfg.get("is_bootstrap", False)
    agent_name = cfg.get("agent_name")

    agent_config = load_agent_config(agent_name) if not is_bootstrap else None
    if requested_model_name:
        model_name = requested_model_name
    else:
        agent_model_name = agent_config.model if agent_config and agent_config.model else _resolve_model_name()
        model_name = agent_model_name

    app_config = get_app_config()
    model_config = app_config.get_model_config(model_name) if model_name else None
    if model_config is None:
        raise ValueError("No chat model could be resolved. Please configure at least one model in config.yaml or provide a valid 'model_name'/'model' in the request.")
    if thinking_enabled and not model_config.supports_thinking:
        logger.warning(f"Thinking mode is enabled but model '{model_name}' does not support it; fallback to non-thinking mode.")
        thinking_enabled = False

    if "metadata" not in config:
        config["metadata"] = {}
    config["metadata"].update(
        {
            "runtime": "coach",
            "agent_name": agent_name or "default",
            "model_name": model_name or "default",
            "thinking_enabled": thinking_enabled,
            "reasoning_effort": reasoning_effort,
            "is_plan_mode": False,
            "subagent_enabled": False,
        }
    )

    if is_bootstrap:
        return create_agent(
            model=create_chat_model(name=model_name, thinking_enabled=thinking_enabled),
            tools=get_available_tools(model_name=model_name, subagent_enabled=False) + [setup_agent],
            middleware=_build_coach_middlewares(config, model_name=model_name),
            system_prompt=apply_prompt_template(subagent_enabled=False, max_concurrent_subagents=max_concurrent_subagents, available_skills=set(["bootstrap"])),
            state_schema=ThreadState,
        )

    return create_agent(
        model=create_chat_model(name=model_name, thinking_enabled=thinking_enabled, reasoning_effort=reasoning_effort),
        tools=get_available_tools(model_name=model_name, groups=agent_config.tool_groups if agent_config else None, subagent_enabled=False),
        middleware=_build_coach_middlewares(config, model_name=model_name, agent_name=agent_name),
        system_prompt=apply_prompt_template(subagent_enabled=False, max_concurrent_subagents=max_concurrent_subagents, agent_name=agent_name),
        state_schema=ThreadState,
    )

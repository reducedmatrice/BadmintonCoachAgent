from __future__ import annotations

import json
from pathlib import Path

import deerflow.tools as tools_module

from deerflow.agents import make_coach_agent
from deerflow.agents.coach_agent import agent as coach_agent_module
from deerflow.config.app_config import AppConfig
from deerflow.config.model_config import ModelConfig
from deerflow.config.sandbox_config import SandboxConfig


def _make_app_config(models: list[ModelConfig]) -> AppConfig:
    return AppConfig(
        models=models,
        sandbox=SandboxConfig(use="deerflow.sandbox.local:LocalSandboxProvider"),
    )


def _make_model(name: str, *, supports_thinking: bool, supports_vision: bool) -> ModelConfig:
    return ModelConfig(
        name=name,
        display_name=name,
        description=None,
        use="langchain_openai:ChatOpenAI",
        model=name,
        supports_thinking=supports_thinking,
        supports_vision=supports_vision,
    )


def test_langgraph_entrypoints_to_make_coach_agent():
    langgraph_path = Path(__file__).resolve().parents[1] / "langgraph.json"
    payload = json.loads(langgraph_path.read_text(encoding="utf-8"))
    assert payload["graphs"]["lead_agent"] == "deerflow.agents:make_coach_agent"


def test_build_coach_middlewares_excludes_todo_and_subagent_limit(monkeypatch):
    app_config = _make_app_config([_make_model("vision-model", supports_thinking=True, supports_vision=True)])
    monkeypatch.setattr(coach_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(coach_agent_module, "_create_summarization_middleware", lambda: None)

    middlewares = coach_agent_module._build_coach_middlewares(
        {"configurable": {"is_plan_mode": True, "subagent_enabled": True}},
        model_name="vision-model",
    )

    names = {type(m).__name__ for m in middlewares}
    assert "ThreadDataMiddleware" in names
    assert "UploadsMiddleware" in names
    assert "SandboxMiddleware" in names
    assert "ToolErrorHandlingMiddleware" in names
    assert "CoachIntakeMiddleware" in names
    assert "MemoryMiddleware" in names
    assert "ViewImageMiddleware" in names
    assert "ClarificationMiddleware" in names
    assert "TodoMiddleware" not in names
    assert "SubagentLimitMiddleware" not in names


def test_make_coach_agent_disables_subagent_and_plan_mode(monkeypatch):
    app_config = _make_app_config([_make_model("coach-model", supports_thinking=True, supports_vision=False)])
    monkeypatch.setattr(coach_agent_module, "get_app_config", lambda: app_config)
    captured: dict[str, object] = {}

    def _fake_get_available_tools(**kwargs):
        captured["tools_kwargs"] = kwargs
        return []

    monkeypatch.setattr(tools_module, "get_available_tools", _fake_get_available_tools)
    monkeypatch.setattr(coach_agent_module, "_build_coach_middlewares", lambda config, model_name, agent_name=None: [])
    monkeypatch.setattr(coach_agent_module, "create_chat_model", lambda **kwargs: object())

    def _fake_prompt_template(**kwargs):
        captured["prompt_kwargs"] = kwargs
        return "coach prompt"

    monkeypatch.setattr(coach_agent_module, "apply_prompt_template", _fake_prompt_template)
    monkeypatch.setattr(coach_agent_module, "create_agent", lambda **kwargs: kwargs)

    result = make_coach_agent(
        {
            "configurable": {
                "model_name": "coach-model",
                "thinking_enabled": True,
                "is_plan_mode": True,
                "subagent_enabled": True,
            }
        }
    )

    assert result["system_prompt"] == "coach prompt"
    assert captured["prompt_kwargs"]["subagent_enabled"] is False
    assert captured["tools_kwargs"]["subagent_enabled"] is False
    assert result["middleware"] == []

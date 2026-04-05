"""Tests for coach clarification short-circuit middleware."""

from __future__ import annotations

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from deerflow.agents.middlewares.coach_clarification_middleware import CoachClarificationMiddleware


def _request(state: dict):
    request = MagicMock()
    request.state = state
    return request


def test_wrap_model_call_short_circuits_when_clarification_request_exists():
    middleware = CoachClarificationMiddleware()
    request = _request(
        {
            "coach_intake": {
                "clarification_request": {
                    "question": "先补一条信息，你现在希望我先帮你做哪类判断？",
                    "clarification_type": "missing_info",
                    "reason": "underspecified_request",
                    "options": ["赛前准备", "赛后复盘", "恢复建议"],
                }
            }
        }
    )
    handler = MagicMock()

    result = middleware.wrap_model_call(request, handler)

    assert isinstance(result, AIMessage)
    assert result.tool_calls[0]["name"] == "ask_clarification"
    assert result.tool_calls[0]["args"]["question"] == "先补一条信息，你现在希望我先帮你做哪类判断？"
    handler.assert_not_called()


def test_wrap_model_call_delegates_when_no_clarification_request():
    middleware = CoachClarificationMiddleware()
    request = _request({"coach_intake": {"clarification_request": None}})
    handler = MagicMock(return_value=AIMessage(content="正常回复"))

    result = middleware.wrap_model_call(request, handler)

    assert isinstance(result, AIMessage)
    assert result.content == "正常回复"
    handler.assert_called_once_with(request)

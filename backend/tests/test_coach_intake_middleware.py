"""Core behaviour tests for CoachIntakeMiddleware."""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage

from deerflow.agents.middlewares.coach_intake_middleware import CoachIntakeMiddleware


def _runtime(thread_id: str | None = "thread-1") -> MagicMock:
    rt = MagicMock()
    rt.context = {"thread_id": thread_id}
    return rt


def test_before_agent_collects_latest_user_input_and_thread_context():
    mw = CoachIntakeMiddleware()
    state = {
        "messages": [
            HumanMessage(content="第一条"),
            AIMessage(content="收到"),
            HumanMessage(content="今晚比赛，帮我做热身计划"),
        ],
        "thread_data": {
            "workspace_path": "/tmp/workspace",
            "uploads_path": "/tmp/uploads",
            "outputs_path": "/tmp/outputs",
        },
    }

    result = mw.before_agent(state, _runtime("thread-xyz"))
    intake = result["coach_intake"]

    assert intake["thread_id"] == "thread-xyz"
    assert intake["latest_user_input"] == "今晚比赛，帮我做热身计划"
    assert intake["message_count"] == 3
    assert intake["thread_data"]["workspace_path"] == "/tmp/workspace"
    assert intake["missing_context"] == []


def test_before_agent_handles_list_content_and_missing_context():
    mw = CoachIntakeMiddleware()
    state = {
        "messages": [
            HumanMessage(content=[{"type": "text", "text": "膝盖有点紧"}, {"type": "text", "text": "想先做恢复"}]),
        ],
    }

    result = mw.before_agent(state, _runtime(thread_id=None))
    intake = result["coach_intake"]

    assert intake["latest_user_input"] == "膝盖有点紧\n想先做恢复"
    assert intake["message_count"] == 1
    assert "thread_id" in intake["missing_context"]
    assert "thread_data" in intake["missing_context"]


def test_before_agent_includes_resolved_persona_from_runtime_context():
    mw = CoachIntakeMiddleware()
    state = {
        "messages": [
            HumanMessage(content="今晚训练前要注意什么"),
        ],
        "thread_data": {
            "workspace_path": "/tmp/workspace",
        },
    }

    runtime = _runtime("thread-persona")
    runtime.context["persona_overrides"] = {
        "session": {"verbosity": "balanced"},
        "task": {"tone": "strict", "route": "health"},
    }

    result = mw.before_agent(state, runtime)
    intake = result["coach_intake"]

    assert intake["persona"] == {
        "tone": "strict",
        "strictness": "medium",
        "verbosity": "balanced",
        "questioning_style": "guided",
        "encouragement_style": "calm",
    }
    assert intake["persona_ignored_overrides"]["session"] == []
    assert "route" in intake["persona_ignored_overrides"]["task"]


def test_before_agent_builds_clarification_request_for_underspecified_query():
    mw = CoachIntakeMiddleware()
    state = {
        "messages": [
            HumanMessage(content="帮我看看"),
        ],
    }

    result = mw.before_agent(state, _runtime("thread-clarify"))
    intake = result["coach_intake"]

    assert intake["intent"]["needs_clarification"] is True
    assert intake["clarification_request"] is not None
    assert intake["clarification_request"]["reason"] in {"low_intent_confidence", "no_stable_intent_detected", "underspecified_request"}
    assert "你现在希望我先帮你做哪类判断" in intake["clarification_request"]["question"]


def test_before_agent_uses_persona_questioning_style_in_clarification_request():
    mw = CoachIntakeMiddleware()
    state = {
        "messages": [
            HumanMessage(content="帮我看下"),
        ],
    }

    runtime = _runtime("thread-direct")
    runtime.context["persona_overrides"] = {
        "task": {"questioning_style": "direct"},
    }

    result = mw.before_agent(state, runtime)
    intake = result["coach_intake"]

    assert intake["intent"]["needs_clarification"] is True
    assert intake["clarification_request"] is not None
    assert intake["clarification_request"]["question"].startswith("直接说，")


def test_before_agent_includes_recall_context_when_policy_returns_one(monkeypatch):
    mw = CoachIntakeMiddleware()
    state = {
        "messages": [
            HumanMessage(content="今晚打球前注意什么"),
        ],
    }

    monkeypatch.setattr(
        "deerflow.agents.middlewares.coach_intake_middleware.build_recall_context",
        lambda **kwargs: {
            "source": "exercise_screenshot",
            "recorded_at": "2026-04-10",
            "summary": "训练负荷较高",
            "risk_level": "high",
            "should_mention": True,
            "mention_reason": "prematch_high_fatigue",
        },
    )

    runtime = _runtime("thread-recall")
    runtime.context["agent_name"] = "badminton-coach"
    result = mw.before_agent(state, runtime)
    intake = result["coach_intake"]

    assert intake["recall_context"] is not None
    assert intake["recall_context"]["should_mention"] is True
    assert intake["recall_context"]["risk_level"] == "high"

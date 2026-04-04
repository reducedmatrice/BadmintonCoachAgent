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

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest

from deerflow.agents.middlewares.clarification_middleware import ClarificationMiddleware
from deerflow.agents.middlewares.coach_clarification_middleware import CoachClarificationMiddleware
from deerflow.agents.middlewares.memory_middleware import MemoryMiddleware
from deerflow.agents.middlewares.request_trace_middleware import append_middleware_trace
from deerflow.agents.middlewares.subagent_limit_middleware import SubagentLimitMiddleware
from deerflow.agents.middlewares.title_middleware import TitleMiddleware
from deerflow.agents.middlewares.todo_middleware import TodoMiddleware
from deerflow.agents.middlewares.tool_error_handling_middleware import ToolErrorHandlingMiddleware
from deerflow.agents.middlewares.thread_data_middleware import ThreadDataMiddleware
from deerflow.agents.middlewares.uploads_middleware import UploadsMiddleware
from deerflow.agents.middlewares.view_image_middleware import ViewImageMiddleware
from deerflow.sandbox.middleware import SandboxMiddleware


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
    assert step["summary"]["enabled"] is True
    assert step["summary"]["agent_name"] == "badminton-coach"
    assert step["summary"]["raw_message_count"] == 2
    assert step["summary"]["filtered_message_count"] == 2
    assert step["summary"]["user_message_count"] == 1
    assert step["summary"]["assistant_message_count"] == 1
    assert step["summary"]["queue_pending_before"] == 0
    assert step["summary"]["queue_pending_after"] == 1
    assert step["summary"]["filtered_user_previews"] == ["明天打球，休闲打"]
    assert step["summary"]["filtered_assistant_previews"] == ["明天休闲打就别把目标定太满。"]


def test_memory_middleware_traces_disabled_skip(monkeypatch):
    monkeypatch.setattr("deerflow.agents.middlewares.memory_middleware.get_memory_config", lambda: SimpleNamespace(enabled=False))

    result = MemoryMiddleware(agent_name="badminton-coach").after_agent(
        {"messages": [HumanMessage(content="hello"), AIMessage(content="hi")]},
        _Runtime({"thread_id": "thread-1", "request_trace_id": "rt_memory"}),
    )

    assert result is not None
    step = result["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.memory"
    assert step["status"] == "skipped"
    assert step["summary"]["enabled"] is False
    assert step["summary"]["reason"] == "memory_disabled"


def test_append_middleware_trace_uses_runtime_trace_id_over_old_state_trace():
    state = {"request_trace": {"trace_id": "rt_old", "steps": [{"name": "old.step", "layer": "middleware", "status": "ok", "timestamp_ms": 1, "summary": {}}]}}

    trace = append_middleware_trace(
        state,
        _Runtime({"request_trace_id": "rt_new"}),
        name="middleware.registry",
        summary={"runtime": "coach"},
    )

    assert trace["trace_id"] == "rt_new"
    assert [step["name"] for step in trace["steps"]] == ["middleware.registry"]


def test_thread_data_middleware_traces_paths(tmp_path):
    result = ThreadDataMiddleware(base_dir=str(tmp_path), lazy_init=True).before_agent(
        {},
        _Runtime({"thread_id": "thread-1", "request_trace_id": "rt_thread_data"}),
    )

    assert result is not None
    assert result["request_trace"]["trace_id"] == "rt_thread_data"
    step = result["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.thread_data"
    assert step["status"] == "ok"
    assert step["summary"]["lazy_init"] is True
    assert step["summary"]["created"] is False
    assert step["summary"]["workspace_path"] == result["thread_data"]["workspace_path"]
    assert step["summary"]["uploads_path"] == result["thread_data"]["uploads_path"]
    assert step["summary"]["outputs_path"] == result["thread_data"]["outputs_path"]


def test_sandbox_middleware_traces_lazy_skip():
    result = SandboxMiddleware(lazy_init=True).before_agent(
        {},
        _Runtime({"thread_id": "thread-1", "request_trace_id": "rt_sandbox"}),
    )

    assert result is not None
    step = result["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.sandbox"
    assert step["status"] == "skipped"
    assert step["summary"]["reason"] == "lazy_init"


def test_sandbox_middleware_traces_eager_acquire_and_release(monkeypatch):
    provider = MagicMock()
    provider.acquire.return_value = "sandbox-1"
    monkeypatch.setattr("deerflow.sandbox.middleware.get_sandbox_provider", lambda: provider)

    middleware = SandboxMiddleware(lazy_init=False)
    runtime = _Runtime({"thread_id": "thread-1", "request_trace_id": "rt_sandbox"})
    before_result = middleware.before_agent({}, runtime)

    assert before_result is not None
    before_step = before_result["request_trace"]["steps"][-1]
    assert before_step["name"] == "middleware.sandbox"
    assert before_step["status"] == "ok"
    assert before_step["summary"]["acquired"] is True

    after_state = {"sandbox": before_result["sandbox"], "request_trace": before_result["request_trace"]}
    after_result = middleware.after_agent(after_state, runtime)

    assert after_result is not None
    after_step = after_result["request_trace"]["steps"][-1]
    assert after_step["name"] == "middleware.sandbox"
    assert after_step["status"] == "ok"
    assert after_step["summary"]["released"] is True
    provider.release.assert_called_once_with("sandbox-1")


def test_uploads_middleware_traces_injected_files(tmp_path):
    uploads_dir = tmp_path / "threads" / "thread-1" / "user-data" / "uploads"
    uploads_dir.mkdir(parents=True)
    (uploads_dir / "clip.mp4").write_bytes(b"video")
    (uploads_dir / "history.csv").write_text("a,b")
    message = HumanMessage(
        content="看一下这个视频",
        additional_kwargs={"files": [{"filename": "clip.mp4", "size": 5, "path": "/mnt/user-data/uploads/clip.mp4"}]},
    )

    result = UploadsMiddleware(base_dir=str(tmp_path)).before_agent(
        {"messages": [message]},
        _Runtime({"thread_id": "thread-1", "request_trace_id": "rt_uploads"}),
    )

    assert result is not None
    step = result["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.uploads"
    assert step["status"] == "ok"
    assert step["summary"]["new_file_count"] == 1
    assert step["summary"]["historical_file_count"] == 1
    assert step["summary"]["filenames"] == ["clip.mp4", "history.csv"]
    assert step["summary"]["extensions"] == [".mp4", ".csv"]
    assert step["summary"]["injected_block"] is True


def test_uploads_middleware_traces_skipped_when_no_uploaded_files(tmp_path):
    result = UploadsMiddleware(base_dir=str(tmp_path)).before_agent(
        {"messages": [HumanMessage(content="plain message")]},
        _Runtime({"thread_id": "thread-1", "request_trace_id": "rt_uploads"}),
    )

    assert result is not None
    step = result["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.uploads"
    assert step["status"] == "skipped"
    assert step["summary"]["reason"] == "no_uploaded_files"
    assert step["summary"]["new_file_count"] == 0
    assert step["summary"]["historical_file_count"] == 0


def test_coach_clarification_middleware_traces_short_circuit():
    request = MagicMock()
    request.state = {
        "request_trace": {"trace_id": "rt_clarification", "steps": []},
        "coach_intake": {
            "clarification_request": {
                "question": "你希望我先看哪一类问题？",
                "missing_slots": ["goal", "time_window"],
            }
        },
    }
    handler = MagicMock()

    result = CoachClarificationMiddleware().wrap_model_call(request, handler)

    assert isinstance(result, AIMessage)
    handler.assert_not_called()
    step = request.state["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.coach_clarification"
    assert step["status"] == "ok"
    assert step["summary"]["short_circuited"] is True
    assert step["summary"]["question"] == "你希望我先看哪一类问题？"
    assert step["summary"]["missing_slots"] == ["goal", "time_window"]


@pytest.mark.anyio
async def test_title_middleware_traces_generated(monkeypatch):
    monkeypatch.setattr("deerflow.agents.middlewares.title_middleware.get_title_config", lambda: SimpleNamespace(enabled=True))
    monkeypatch.setattr(TitleMiddleware, "_generate_title", AsyncMock(return_value="代码总结"))

    result = await TitleMiddleware().aafter_model(
        {"messages": [HumanMessage(content="帮我总结代码"), AIMessage(content="可以")]},
        _Runtime({"thread_id": "thread-1", "request_trace_id": "rt_title"}),
    )

    assert result is not None
    assert result["title"] == "代码总结"
    step = result["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.title"
    assert step["status"] == "ok"
    assert step["summary"]["generated"] is True
    assert step["summary"]["title"] == "代码总结"


@pytest.mark.anyio
async def test_title_middleware_traces_skipped(monkeypatch):
    monkeypatch.setattr("deerflow.agents.middlewares.title_middleware.get_title_config", lambda: SimpleNamespace(enabled=False))

    result = await TitleMiddleware().aafter_model(
        {"messages": [HumanMessage(content="Q"), AIMessage(content="A")]},
        _Runtime({"thread_id": "thread-1", "request_trace_id": "rt_title"}),
    )

    assert result is not None
    step = result["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.title"
    assert step["status"] == "skipped"
    assert step["summary"]["reason"] == "not_first_exchange_or_disabled"


def test_view_image_middleware_traces_injected_without_base64():
    ai_msg = AIMessage(
        content="",
        tool_calls=[{"name": "view_image", "id": "view-1", "args": {"path": "shot.png"}}],
    )
    state = {
        "messages": [ai_msg, ToolMessage(content="ok", tool_call_id="view-1", name="view_image")],
        "viewed_images": {"shot.png": {"mime_type": "image/png", "base64": "SECRET_BASE64"}},
    }

    result = ViewImageMiddleware().before_model(state, _Runtime({"request_trace_id": "rt_view"}))

    assert result is not None
    step = result["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.view_image"
    assert step["status"] == "ok"
    assert step["summary"] == {"injected": True, "viewed_image_count": 1}
    assert "SECRET_BASE64" not in str(step)


def test_view_image_middleware_traces_skipped_when_no_completed_view_image():
    result = ViewImageMiddleware().before_model(
        {"messages": [HumanMessage(content="hello")]},
        _Runtime({"request_trace_id": "rt_view"}),
    )

    assert result is not None
    step = result["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.view_image"
    assert step["status"] == "skipped"
    assert step["summary"]["reason"] == "no_completed_view_image"


def test_clarification_middleware_traces_intercepted():
    request = ToolCallRequest(
        tool_call={
            "name": "ask_clarification",
            "id": "clarify-1",
            "args": {"question": "选哪个方向？", "options": ["A", "B"]},
        },
        tool=None,
        state={"request_trace": {"trace_id": "rt_clarify", "steps": []}},
        runtime=MagicMock(context={"request_trace_id": "rt_clarify"}),
    )

    result = ClarificationMiddleware().wrap_tool_call(request, MagicMock())

    step = result.update["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.clarification"
    assert step["status"] == "ok"
    assert step["summary"]["intercepted"] is True
    assert step["summary"]["question"] == "选哪个方向？"
    assert step["summary"]["options_count"] == 2


def test_tool_error_handling_middleware_traces_error():
    request = ToolCallRequest(
        tool_call={"name": "web_search", "id": "tool-1", "args": {}},
        tool=None,
        state={"request_trace": {"trace_id": "rt_tool_error", "steps": []}},
        runtime=MagicMock(context={"request_trace_id": "rt_tool_error"}),
    )

    def _boom(_request):
        raise RuntimeError("network down")

    result = ToolErrorHandlingMiddleware().wrap_tool_call(request, _boom)

    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    step = request.state["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.tool_error_handling"
    assert step["status"] == "error"
    assert step["summary"]["tool_name"] == "web_search"
    assert step["summary"]["tool_call_id"] == "tool-1"
    assert step["summary"]["error_type"] == "RuntimeError"


def test_todo_middleware_traces_reminder_injection():
    result = TodoMiddleware().before_model(
        {
            "messages": [HumanMessage(content="继续做计划")],
            "todos": [{"content": "补 middleware trace", "status": "in_progress"}],
        },
        _Runtime({"request_trace_id": "rt_todo"}),
    )

    assert result is not None
    step = result["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.todo"
    assert step["status"] == "ok"
    assert step["summary"] == {"injected_reminder": True, "todo_count": 1}


def test_subagent_limit_middleware_traces_truncated_task_calls():
    msg = AIMessage(
        content="",
        tool_calls=[
            {"name": "task", "id": "task-1", "args": {"description": "one"}},
            {"name": "task", "id": "task-2", "args": {"description": "two"}},
            {"name": "task", "id": "task-3", "args": {"description": "three"}},
        ],
    )

    result = SubagentLimitMiddleware(max_concurrent=2).after_model(
        {"messages": [msg]},
        _Runtime({"request_trace_id": "rt_subagent_limit"}),
    )

    assert result is not None
    assert len(result["messages"][0].tool_calls) == 2
    step = result["request_trace"]["steps"][-1]
    assert step["name"] == "middleware.subagent_limit"
    assert step["status"] == "ok"
    assert step["summary"] == {
        "max_concurrent": 2,
        "task_call_count": 3,
        "dropped_count": 1,
    }

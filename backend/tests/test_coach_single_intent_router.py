"""Tests for single-intent coach router."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from deerflow.config.paths import Paths
from deerflow.domain.coach.intent import normalize_intent_payload
from deerflow.domain.coach.router import route_single_intent


def _make_paths(base_dir: Path) -> Paths:
    return Paths(base_dir=base_dir)


def test_route_single_intent_hits_prematch_chain():
    result = route_single_intent("今晚打双打，赛前怎么热身？", memory_data={"facts": []})

    assert result.route == "prematch"
    assert result.payload["chain"] == "prematch"
    assert result.payload["focus_points"]
    assert result.payload["warmup"]
    assert result.payload["persisted"] is False


def test_route_single_intent_hits_postmatch_chain_without_persist():
    result = route_single_intent("今天打完后场步法还是慢，回位跟不上，帮我复盘。")

    assert result.route == "postmatch"
    assert result.payload["chain"] == "postmatch"
    assert result.payload["persisted"] is False
    assert isinstance(result.payload["next_focus"], list)


def test_route_single_intent_hits_health_chain():
    result = route_single_intent("昨晚睡眠 5小时18分钟 HRV 28，今天怎么恢复？")

    assert result.route == "health"
    assert result.payload["chain"] == "health"
    assert result.payload["risk_level"] in {"low", "medium", "high"}
    assert result.payload["recovery_actions"]
    assert result.payload["persisted"] is False


def test_route_single_intent_hits_fallback_chain():
    result = route_single_intent("你好")

    assert result.route == "fallback"
    assert result.payload["chain"] == "fallback"
    assert "follow_up_question" in result.payload


def test_route_single_intent_hits_check_memory_chain(tmp_path: Path):
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = route_single_intent(
            "你现在记得我什么？把我的语言偏好改成中文简洁一点，以后主动提醒我热身。",
            memory_data={
                "user": {
                    "personalContext": {
                        "summary": "用户偏双打，偏巧劲控制。",
                    }
                },
                "facts": [],
            },
        )

    assert result.route == "check_memory"
    assert result.payload["chain"] == "check_memory"
    assert result.payload["persisted"] is True
    assert result.payload["updates"]["preferred_language"] == "zh-CN"
    assert result.payload["updates"]["wants_proactive_reminder"] is True
    assert "长期记忆摘要" in "\n".join(result.payload["summary_lines"])


def test_route_single_intent_applies_health_strong_rule_override():
    forced_prematch = normalize_intent_payload(
        {
            "primary_intent": "prematch",
            "secondary_intents": [],
            "slots": {"session_goal": "今晚打球"},
            "missing_slots": [],
            "risk_level": "low",
        }
    )

    result = route_single_intent("赛前计划先不说了，我现在膝盖刺痛。", intent=forced_prematch)

    assert result.route == "health"
    assert result.payload["chain"] == "health"


def test_route_single_intent_persist_postmatch_writes_review_log(tmp_path: Path):
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        with patch("deerflow.domain.coach.prematch.get_paths", return_value=_make_paths(tmp_path)):
            result = route_single_intent(
                "今天后场步法还是慢，回位总跟不上。下次重点继续盯后场启动。",
                persist_postmatch=True,
            )

    assert result.route == "postmatch"
    assert result.payload["persisted"] is True
    review_log_path = Path(result.payload["review_log_path"])
    assert review_log_path.exists()


def test_route_single_intent_persist_health_writes_profile(tmp_path: Path):
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = route_single_intent(
            "昨晚睡眠 5小时18分钟 HRV 28，今天怎么恢复？",
            persist_postmatch=True,
        )

    assert result.route == "health"
    assert result.payload["persisted"] is True
    profile_path = Path(result.payload["profile_path"])
    assert profile_path.exists()


def test_route_single_intent_persist_prematch_writes_only_when_signal_is_stable(tmp_path: Path):
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        with patch("deerflow.domain.coach.prematch.get_paths", return_value=_make_paths(tmp_path)):
            result = route_single_intent(
                "我平时久坐，这两周准备比赛，今晚双打优先练后场步法。",
                persist_postmatch=True,
            )

    assert result.route == "prematch"
    assert result.payload["persisted"] is True
    assert "constraints" in result.payload["writeback"]
    assert "recent_goals" in result.payload["writeback"]
    profile_path = Path(result.payload["profile_path"])
    assert profile_path.exists()


def _write_profile(base_dir: Path, profile: dict) -> None:
    agent_dir = base_dir / "agents" / "badminton-coach"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "coach_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _read_profile(base_dir: Path) -> dict:
    profile_path = base_dir / "agents" / "badminton-coach" / "coach_profile.json"
    return json.loads(profile_path.read_text(encoding="utf-8"))


def test_route_prematch_injects_training_data(tmp_path: Path):
    profile = {
        "training_log": [
            {"date": "2026-05-19", "session_type": "match", "summary": "双打", "focus_areas": ["反手"], "issues": [], "improvements": []},
            {"date": "2026-05-21", "session_type": "training", "summary": "步法", "focus_areas": ["步法"], "issues": [], "improvements": []},
        ],
        "body_metrics": [
            {"date": "2026-05-19", "avg_heart_rate": 140, "fatigue_level": "low"},
            {"date": "2026-05-21", "avg_heart_rate": 150, "fatigue_level": "medium"},
        ],
    }
    _write_profile(tmp_path, profile)

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = route_single_intent("今晚打双打，赛前怎么热身？", memory_data={"facts": []})

    assert result.route == "prematch"
    assert "recent_training" in result.payload
    assert "body_trend" in result.payload


def test_route_prematch_degrades_gracefully(tmp_path: Path):
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = route_single_intent("今晚打双打，赛前怎么热身？", memory_data={"facts": []})

    assert result.route == "prematch"
    assert result.payload.get("recent_training_degraded") is True


def test_route_postmatch_writes_training_log(tmp_path: Path):
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = route_single_intent("今天打完后场步法还是慢，回位跟不上。", persist_postmatch=True)

    assert result.route == "postmatch"
    assert result.payload["training_log_persisted"] is True

    profile = _read_profile(tmp_path)
    assert len(profile.get("training_log", [])) >= 1


def test_route_health_writes_body_metric(tmp_path: Path):
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = route_single_intent(
            "昨晚睡眠 5小时18分钟 HRV 28，今天怎么恢复？",
            persist_postmatch=True,
        )

    assert result.route == "health"
    assert result.payload["body_metric_persisted"] is True

    profile = _read_profile(tmp_path)
    assert len(profile.get("body_metrics", [])) >= 1

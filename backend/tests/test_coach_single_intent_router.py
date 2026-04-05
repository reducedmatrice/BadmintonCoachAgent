"""Tests for single-intent coach router."""

from __future__ import annotations

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

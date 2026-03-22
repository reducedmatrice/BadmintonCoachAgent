"""Tests for coach profile persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from deerflow.config.paths import Paths
from deerflow.domain.coach.postmatch import PostmatchReview, TechnicalObservation, Improvement
from deerflow.domain.coach.profile_store import append_review_log, update_profile_from_postmatch


def _make_paths(base_dir: Path) -> Paths:
    return Paths(base_dir=base_dir)


def test_update_profile_merges_weakness_and_recent_review(tmp_path: Path):
    agent_dir = tmp_path / "agents" / "badminton-coach"
    agent_dir.mkdir(parents=True)
    existing_profile = {
        "tech_profile": {
            "focus_topics": ["后场步法"],
            "weaknesses": [
                {
                    "name": "后场步法回位慢",
                    "severity": 0.6,
                    "trend": "stable",
                    "last_seen_at": "2026-03-20",
                    "evidence": "旧记录",
                }
            ],
            "strengths": [],
            "recent_reviews": [],
        }
    }
    (agent_dir / "coach_profile.json").write_text(json.dumps(existing_profile), encoding="utf-8")

    review = PostmatchReview(
        technical_observations=[TechnicalObservation(topic="后场步法", finding="回位慢", severity=0.8, evidence="后场球后续衔接不上")],
        improvements=[Improvement(topic="反手稳定性", evidence="今天反手更敢发力了")],
        next_focus=["后场步法", "反手稳定性"],
        emotional_notes=[],
        summary="识别到 1 条技术问题；1 条进步点",
    )

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        updated = update_profile_from_postmatch(review, occurred_at=datetime(2026, 3, 23, 12, 0, tzinfo=UTC))

    weakness = updated["tech_profile"]["weaknesses"][0]
    assert weakness["severity"] == 0.8
    assert weakness["last_seen_at"] == "2026-03-23"
    assert "反手稳定性" in updated["tech_profile"]["focus_topics"]
    assert updated["tech_profile"]["recent_reviews"][-1]["next_focus"] == ["后场步法", "反手稳定性"]


def test_append_review_log_writes_expected_sections(tmp_path: Path):
    review = PostmatchReview(
        technical_observations=[TechnicalObservation(topic="后场步法", finding="回位慢", severity=0.7, evidence="回位总跟不上")],
        improvements=[Improvement(topic="反手稳定性", evidence="反手更稳了")],
        next_focus=["后场步法"],
        emotional_notes=[],
        summary="识别到 1 条技术问题；1 条进步点",
    )

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        log_path = append_review_log(review, occurred_at=datetime(2026, 3, 23, 12, 30, tzinfo=UTC))

    content = log_path.read_text(encoding="utf-8")
    assert "技术问题" in content
    assert "进步点" in content
    assert "下次重点" in content
    assert "后场步法" in content

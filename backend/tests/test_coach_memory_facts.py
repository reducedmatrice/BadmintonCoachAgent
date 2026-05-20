"""Tests for rule-based memory fact extraction from training data."""

from __future__ import annotations

from deerflow.domain.coach.profile_store import extract_body_facts, extract_training_facts


def test_extract_training_facts_repeated_focus_areas():
    log = [
        {"date": "2026-05-17", "focus_areas": ["反手", "网前"], "issues": [], "improvements": []},
        {"date": "2026-05-19", "focus_areas": ["反手"], "issues": [], "improvements": []},
        {"date": "2026-05-21", "focus_areas": ["反手", "步法"], "issues": [], "improvements": []},
    ]
    facts = extract_training_facts(log)
    assert any("反手" in f["content"] and "反复训练" in f["content"] for f in facts)
    assert all(f["source"] == "training_log" for f in facts)


def test_extract_training_facts_repeated_issues():
    log = [
        {"date": "2026-05-17", "focus_areas": [], "issues": ["反手过渡出界"], "improvements": []},
        {"date": "2026-05-19", "focus_areas": [], "issues": ["反手过渡出界"], "improvements": []},
        {"date": "2026-05-21", "focus_areas": [], "issues": ["反手过渡出界"], "improvements": []},
    ]
    facts = extract_training_facts(log)
    assert any("反手过渡出界" in f["content"] and "持续存在" in f["content"] for f in facts)
    assert any(f["category"] == "knowledge" for f in facts)


def test_extract_training_facts_improvement():
    log = [
        {"date": "2026-05-19", "focus_areas": [], "issues": [], "improvements": ["发球质量提升"]},
        {"date": "2026-05-21", "focus_areas": [], "issues": [], "improvements": ["发球质量提升"]},
    ]
    facts = extract_training_facts(log)
    assert any("发球质量提升" in f["content"] and "进步" in f["content"] for f in facts)


def test_extract_training_facts_no_match():
    log = [
        {"date": "2026-05-21", "focus_areas": ["反手"], "issues": ["失误"], "improvements": ["稳"]},
    ]
    facts = extract_training_facts(log)
    assert len(facts) == 0


def test_extract_body_facts_fatigue():
    metrics = [
        {"date": "2026-05-17", "fatigue_level": "high"},
        {"date": "2026-05-19", "fatigue_level": "high"},
        {"date": "2026-05-21", "fatigue_level": "high"},
    ]
    facts = extract_body_facts(metrics)
    assert any("疲劳" in f["content"] for f in facts)
    assert any(f["confidence"] == 0.9 for f in facts)


def test_extract_body_facts_heart_rate_rising():
    metrics = [
        {"date": "2026-05-15", "avg_heart_rate": 140},
        {"date": "2026-05-17", "avg_heart_rate": 145},
        {"date": "2026-05-19", "avg_heart_rate": 150},
        {"date": "2026-05-21", "avg_heart_rate": 155},
    ]
    facts = extract_body_facts(metrics)
    assert any("强度" in f["content"] and "上升" in f["content"] for f in facts)


def test_extract_body_facts_high_calories():
    metrics = [
        {"date": "2026-05-21", "calories_kcal": 850},
    ]
    facts = extract_body_facts(metrics)
    assert any("消耗" in f["content"] and "850" in f["content"] for f in facts)


def test_extract_body_facts_no_match():
    metrics = [
        {"date": "2026-05-21", "fatigue_level": "low", "avg_heart_rate": 130, "calories_kcal": 500},
    ]
    facts = extract_body_facts(metrics)
    assert len(facts) == 0

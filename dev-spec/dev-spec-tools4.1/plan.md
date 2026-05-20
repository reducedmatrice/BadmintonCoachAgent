# Coach Tool Capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- []`) syntax for tracking.

**Goal:** Add training log management, body metrics trend analysis, deterministic router-layer tool injection with degrade/fallback, rule-based memory fact extraction, and logging to the coach domain.

**Architecture:** Three-layer design — (1) data storage in coach_profile.json with training_log[] and body_metrics[], (2) read tools in training_data.py following weather.py degrade pattern + BaseTool registration, (3) memory facts sync via rule-based extraction after writes. All operations logged via Python logging module.

**Tech Stack:** Python 3.12, dataclasses, json, logging, langchain BaseTool, existing deerflow harness patterns.

---

## File Structure

| File | Responsibility |
|---|---|
| `domain/coach/training_data.py` | Read tools: context dataclasses + get_recent_training_log + get_body_metrics_trend + trend computation |
| `domain/coach/profile_store.py` | Write functions: append_training_log + append_body_metric + extract_training_facts + extract_body_facts + logger |
| `domain/coach/router.py` | Router integration: inject training data into prematch/health payloads, write data in postmatch/health |
| `domain/coach/response_renderer.py` | Render degraded training data in prematch/health responses |
| `domain/coach/__init__.py` | Export new types and functions |
| `tools/builtins/training_tools.py` | BaseTool definitions: query_training_log + get_body_metrics_trend_tool |
| `tools/tools.py` | Register new BaseTools in BUILTIN_TOOLS |
| `tests/test_training_data.py` | Unit tests for training_data.py (read tools, degrade, trend) |
| `tests/test_training_log_write.py` | Unit tests for write functions (append, cap at 200) |
| `tests/test_coach_memory_facts.py` | Unit tests for fact extraction rules |
| `tests/test_training_basetools.py` | Unit tests for BaseTool invocation |

---

### Task 1: training_data.py — context dataclasses and read functions

**Files:**
- Create: `backend/packages/harness/deerflow/domain/coach/training_data.py`
- Test: `backend/tests/test_training_data.py`

- [ ] **Step 1: Write failing tests for TrainingLogContext and get_recent_training_log**

```python
# backend/tests/test_training_data.py
"""Tests for training data read tools."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from deerflow.config.paths import Paths
from deerflow.domain.coach.training_data import (
    BodyMetricsContext,
    TrainingLogContext,
    get_body_metrics_trend,
    get_recent_training_log,
)


def _make_paths(base_dir: Path) -> Paths:
    return Paths(base_dir=base_dir)


def _write_profile(base_dir: Path, profile: dict) -> None:
    agent_dir = base_dir / "badminton-coach"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "coach_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def test_get_recent_training_log_returns_entries(tmp_path: Path):
    profile = {
        "training_log": [
            {"date": "2026-05-19", "session_type": "training", "summary": "反手练习"},
            {"date": "2026-05-20", "session_type": "match", "summary": "双打3局"},
            {"date": "2026-05-21", "session_type": "training", "summary": "步法训练"},
        ]
    }
    _write_profile(tmp_path, profile)

    with patch("deerflow.domain.coach.training_data.get_paths", return_value=_make_paths(tmp_path)):
        ctx = get_recent_training_log(2)

    assert not ctx.degraded
    assert ctx.total_count == 3
    assert len(ctx.entries) == 2
    assert ctx.entries[0]["date"] == "2026-05-21"


def test_get_recent_training_log_filters_by_session_type(tmp_path: Path):
    profile = {
        "training_log": [
            {"date": "2026-05-19", "session_type": "training", "summary": "反手练习"},
            {"date": "2026-05-20", "session_type": "match", "summary": "双打3局"},
            {"date": "2026-05-21", "session_type": "training", "summary": "步法训练"},
        ]
    }
    _write_profile(tmp_path, profile)

    with patch("deerflow.domain.coach.training_data.get_paths", return_value=_make_paths(tmp_path)):
        ctx = get_recent_training_log(5, session_type="match")

    assert not ctx.degraded
    assert len(ctx.entries) == 1
    assert ctx.entries[0]["session_type"] == "match"


def test_get_recent_training_log_degrades_on_empty(tmp_path: Path):
    _write_profile(tmp_path, {"training_log": []})

    with patch("deerflow.domain.coach.training_data.get_paths", return_value=_make_paths(tmp_path)):
        ctx = get_recent_training_log(5)

    assert ctx.degraded
    assert ctx.degrade_reason == "no_training_log_entries"


def test_get_recent_training_log_degrades_on_missing_profile(tmp_path: Path):
    with patch("deerflow.domain.coach.training_data.get_paths", return_value=_make_paths(tmp_path)):
        ctx = get_recent_training_log(5)

    assert ctx.degraded
    assert ctx.degrade_reason == "profile_not_found"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_training_data.py -v`
Expected: FAIL — module `deerflow.domain.coach.training_data` does not exist

- [ ] **Step 3: Create training_data.py with TrainingLogContext and get_recent_training_log**

```python
# backend/packages/harness/deerflow/domain/coach/training_data.py
"""Read tools for training log and body metrics, following weather.py degrade pattern."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from deerflow.config.paths import get_paths

logger = logging.getLogger(__name__)

_MAX_TRAINING_LOG = 200
_MAX_BODY_METRICS = 200


@dataclass
class TrainingLogContext:
    entries: list[dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    source: str = "coach_profile"
    degraded: bool = False
    degrade_reason: str = ""


@dataclass
class BodyMetricsContext:
    entries: list[dict[str, Any]] = field(default_factory=list)
    trend_summary: dict[str, Any] = field(default_factory=dict)
    source: str = "coach_profile"
    degraded: bool = False
    degrade_reason: str = ""


def get_recent_training_log(
    n: int,
    *,
    session_type: str | None = None,
    agent_name: str = "badminton-coach",
) -> TrainingLogContext:
    """Read the most recent N training log entries from coach_profile."""
    profile = _load_profile(agent_name)
    if profile is None:
        logger.warning("[coach] get_recent_training_log: degraded reason=profile_not_found")
        return TrainingLogContext(degraded=True, degrade_reason="profile_not_found")

    raw_log = profile.get("training_log")
    if not isinstance(raw_log, list) or not raw_log:
        logger.warning("[coach] get_recent_training_log: degraded reason=no_training_log_entries")
        return TrainingLogContext(degraded=True, degrade_reason="no_training_log_entries")

    entries = [item for item in raw_log if isinstance(item, dict)]
    if session_type:
        entries = [e for e in entries if e.get("session_type") == session_type]

    if not entries:
        logger.warning(
            "[coach] get_recent_training_log: degraded reason=no_matching_entries session_type=%s",
            session_type,
        )
        return TrainingLogContext(
            total_count=len(raw_log) if isinstance(raw_log, list) else 0,
            degraded=True,
            degrade_reason="no_matching_entries",
        )

    entries.sort(key=lambda e: e.get("date", ""), reverse=True)
    selected = entries[:n]

    logger.info(
        "[coach] get_recent_training_log: loaded %d entries (degraded=False)",
        len(selected),
    )
    return TrainingLogContext(
        entries=selected,
        total_count=len(entries),
    )


def get_body_metrics_trend(
    days: int = 14,
    *,
    agent_name: str = "badminton-coach",
) -> BodyMetricsContext:
    """Read recent body metrics and compute a trend summary."""
    profile = _load_profile(agent_name)
    if profile is None:
        logger.warning("[coach] get_body_metrics_trend: degraded reason=profile_not_found")
        return BodyMetricsContext(degraded=True, degrade_reason="profile_not_found")

    raw_metrics = profile.get("body_metrics")
    if not isinstance(raw_metrics, list) or len(raw_metrics) < 2:
        logger.warning("[coach] get_body_metrics_trend: degraded reason=insufficient_data")
        return BodyMetricsContext(degraded=True, degrade_reason="insufficient_data")

    entries = [item for item in raw_metrics if isinstance(item, dict)]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    recent = [e for e in entries if e.get("date", "") >= cutoff]

    if len(recent) < 2:
        logger.warning("[coach] get_body_metrics_trend: degraded reason=insufficient_recent_data")
        return BodyMetricsContext(
            entries=recent,
            degraded=True,
            degrade_reason="insufficient_recent_data",
        )

    trend_summary = _compute_trend_summary(recent)
    logger.info(
        "[coach] get_body_metrics_trend: loaded %d entries over %d days (degraded=False)",
        len(recent),
        days,
    )
    return BodyMetricsContext(entries=recent, trend_summary=trend_summary)


def _compute_trend_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute trend metrics from body metrics entries."""
    hr_values = [e["avg_heart_rate"] for e in entries if isinstance(e.get("avg_heart_rate"), (int, float))]
    load_values = [e["training_load"] for e in entries if isinstance(e.get("training_load"), (int, float))]
    fatigue_levels = [e.get("fatigue_level", "") for e in entries if e.get("fatigue_level")]

    summary: dict[str, Any] = {}

    if len(hr_values) >= 2:
        first_half = hr_values[: len(hr_values) // 2]
        second_half = hr_values[len(hr_values) // 2 :]
        summary["avg_heart_rate_trend"] = "rising" if _mean(second_half) > _mean(first_half) else "stable_or_declining"
        summary["avg_heart_rate_mean"] = round(_mean(hr_values), 1)

    if len(load_values) >= 2:
        first_half = load_values[: len(load_values) // 2]
        second_half = load_values[len(load_values) // 2 :]
        summary["training_load_trend"] = "rising" if _mean(second_half) > _mean(first_half) else "stable_or_declining"
        summary["training_load_mean"] = round(_mean(load_values), 1)

    if fatigue_levels:
        high_count = fatigue_levels.count("high")
        summary["fatigue_high_ratio"] = round(high_count / len(fatigue_levels), 2)
        summary["dominant_fatigue"] = max(set(fatigue_levels), key=fatigue_levels.count)

    return summary


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _load_profile(agent_name: str) -> dict[str, Any] | None:
    from deerflow.domain.coach.profile_store import load_coach_profile

    try:
        return load_coach_profile(agent_name)
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_training_data.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/domain/coach/training_data.py backend/tests/test_training_data.py
git commit -m "feat(coach): add training_data.py with TrainingLogContext and read tools"
```

---

### Task 2: training_data.py — BodyMetricsContext and get_body_metrics_trend tests

**Files:**
- Modify: `backend/packages/harness/deerflow/domain/coach/training_data.py`
- Test: `backend/tests/test_training_data.py`

- [ ] **Step 1: Add failing tests for get_body_metrics_trend**

Append to `backend/tests/test_training_data.py`:

```python
def test_get_body_metrics_trend_returns_summary(tmp_path: Path):
    profile = {
        "body_metrics": [
            {"date": "2026-05-15", "avg_heart_rate": 140, "training_load": 100, "fatigue_level": "low"},
            {"date": "2026-05-17", "avg_heart_rate": 145, "training_load": 115, "fatigue_level": "medium"},
            {"date": "2026-05-19", "avg_heart_rate": 150, "training_load": 130, "fatigue_level": "medium"},
            {"date": "2026-05-21", "avg_heart_rate": 155, "training_load": 140, "fatigue_level": "high"},
        ]
    }
    _write_profile(tmp_path, profile)

    with patch("deerflow.domain.coach.training_data.get_paths", return_value=_make_paths(tmp_path)):
        ctx = get_body_metrics_trend(14)

    assert not ctx.degraded
    assert len(ctx.entries) == 4
    assert ctx.trend_summary["avg_heart_rate_trend"] == "rising"
    assert ctx.trend_summary["training_load_trend"] == "rising"
    assert ctx.trend_summary["fatigue_high_ratio"] == 0.25
    assert ctx.trend_summary["dominant_fatigue"] == "medium"


def test_get_body_metrics_trend_degrades_on_insufficient_data(tmp_path: Path):
    _write_profile(tmp_path, {"body_metrics": [
        {"date": "2026-05-21", "avg_heart_rate": 150},
    ]})

    with patch("deerflow.domain.coach.training_data.get_paths", return_value=_make_paths(tmp_path)):
        ctx = get_body_metrics_trend(14)

    assert ctx.degraded
    assert ctx.degrade_reason == "insufficient_data"


def test_get_body_metrics_trend_degrades_on_missing_profile(tmp_path: Path):
    with patch("deerflow.domain.coach.training_data.get_paths", return_value=_make_paths(tmp_path)):
        ctx = get_body_metrics_trend(14)

    assert ctx.degraded
    assert ctx.degrade_reason == "profile_not_found"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_training_data.py::test_get_body_metrics_trend_returns_summary -v`
Expected: FAIL — `get_body_metrics_trend` function is already defined but trend summary logic isn't tested yet (actually should PASS since we already have the function). Let me verify...

Actually the function already exists in Step 3 of Task 1. These tests should PASS. Let me restructure — these are actually "run and verify pass" tests since the implementation already covers them.

- [ ] **Step 2 (revised): Run tests to verify they pass**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_training_data.py -v`
Expected: 7 tests PASS (4 from Task 1 + 3 new)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_training_data.py
git commit -m "test(coach): add body metrics trend tests"
```

---

### Task 3: profile_store.py — append_training_log with logger

**Files:**
- Modify: `backend/packages/harness/deerflow/domain/coach/profile_store.py`
- Test: `backend/tests/test_training_log_write.py`

- [ ] **Step 1: Write failing tests for append_training_log**

```python
# backend/tests/test_training_log_write.py
"""Tests for training log and body metric write functions."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from deerflow.config.paths import Paths
from deerflow.domain.coach.profile_store import (
    append_body_metric,
    append_training_log,
    load_coach_profile,
)


def _make_paths(base_dir: Path) -> Paths:
    return Paths(base_dir=base_dir)


def _read_profile(base_dir: Path) -> dict:
    profile_path = base_dir / "badminton-coach" / "coach_profile.json"
    return json.loads(profile_path.read_text(encoding="utf-8"))


def test_append_training_log_creates_new_entry(tmp_path: Path):
    entry = {
        "date": "2026-05-21",
        "session_type": "match",
        "match_format": "doubles",
        "summary": "双打3局，反手失误多",
        "focus_areas": ["反手"],
        "improvements": [],
        "issues": ["反手过渡出界"],
        "source": "postmatch",
    }

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result_path = append_training_log(entry)

    assert result_path.exists()
    profile = _read_profile(tmp_path)
    assert len(profile["training_log"]) == 1
    assert profile["training_log"][0]["summary"] == "双打3局，反手失误多"


def test_append_training_log_caps_at_200(tmp_path: Path):
    existing_log = [
        {"date": f"2026-{i:02d}-01", "session_type": "training", "summary": f"训练{i}"}
        for i in range(1, 201)
    ]
    agent_dir = tmp_path / "badminton-coach"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "coach_profile.json").write_text(
        json.dumps({"training_log": existing_log}, ensure_ascii=False), encoding="utf-8"
    )

    new_entry = {"date": "2026-05-21", "session_type": "match", "summary": "新记录"}

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        append_training_log(new_entry)

    profile = _read_profile(tmp_path)
    assert len(profile["training_log"]) == 200
    assert profile["training_log"][-1]["summary"] == "新记录"
    assert profile["training_log"][0]["summary"] == "训练2"


def test_append_body_metric_creates_new_entry(tmp_path: Path):
    entry = {
        "date": "2026-05-21",
        "fatigue_level": "medium",
        "avg_heart_rate": 145,
        "source": "exercise_screenshot",
    }

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result_path = append_body_metric(entry)

    assert result_path.exists()
    profile = _read_profile(tmp_path)
    assert len(profile["body_metrics"]) == 1
    assert profile["body_metrics"][0]["fatigue_level"] == "medium"


def test_append_body_metric_caps_at_200(tmp_path: Path):
    existing_metrics = [
        {"date": f"2026-{i:02d}-01", "fatigue_level": "low", "source": "manual"}
        for i in range(1, 201)
    ]
    agent_dir = tmp_path / "badminton-coach"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "coach_profile.json").write_text(
        json.dumps({"body_metrics": existing_metrics}, ensure_ascii=False), encoding="utf-8"
    )

    new_entry = {"date": "2026-05-21", "fatigue_level": "high", "source": "health_report"}

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        append_body_metric(new_entry)

    profile = _read_profile(tmp_path)
    assert len(profile["body_metrics"]) == 200
    assert profile["body_metrics"][-1]["fatigue_level"] == "high"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_training_log_write.py -v`
Expected: FAIL — `append_training_log` and `append_body_metric` not defined

- [ ] **Step 3: Add append_training_log and append_body_metric to profile_store.py**

Add logger at the top of profile_store.py:

```python
import logging

logger = logging.getLogger(__name__)
```

Add after `save_coach_profile`:

```python
_MAX_TRAINING_LOG = 200
_MAX_BODY_METRICS = 200


def append_training_log(
    entry: dict[str, Any],
    *,
    agent_name: str = "badminton-coach",
) -> Path:
    """Append a training log entry to coach_profile.json, capped at 200."""
    profile = load_coach_profile(agent_name)
    training_log = list(profile.get("training_log", []))
    if not isinstance(training_log, list):
        training_log = []

    training_log.append(entry)
    if len(training_log) > _MAX_TRAINING_LOG:
        training_log = training_log[-_MAX_TRAINING_LOG:]

    profile["training_log"] = training_log
    profile["last_updated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    try:
        result_path = save_coach_profile(profile, agent_name)
        logger.info(
            "[coach] append_training_log: persisted entry date=%s source=%s",
            entry.get("date", ""),
            entry.get("source", ""),
        )
        return result_path
    except Exception as exc:
        logger.error("[coach] append_training_log: failed — %s", exc, exc_info=True)
        raise


def append_body_metric(
    entry: dict[str, Any],
    *,
    agent_name: str = "badminton-coach",
) -> Path:
    """Append a body metrics entry to coach_profile.json, capped at 200."""
    profile = load_coach_profile(agent_name)
    body_metrics = list(profile.get("body_metrics", []))
    if not isinstance(body_metrics, list):
        body_metrics = []

    body_metrics.append(entry)
    if len(body_metrics) > _MAX_BODY_METRICS:
        body_metrics = body_metrics[-_MAX_BODY_METRICS:]

    profile["body_metrics"] = body_metrics
    profile["last_updated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    try:
        result_path = save_coach_profile(profile, agent_name)
        logger.info(
            "[coach] append_body_metric: persisted entry date=%s source=%s",
            entry.get("date", ""),
            entry.get("source", ""),
        )
        return result_path
    except Exception as exc:
        logger.error("[coach] append_body_metric: failed — %s", exc, exc_info=True)
        raise
```

Also add `import logging` at the top if not present, and ensure `datetime, UTC` are imported.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_training_log_write.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/domain/coach/profile_store.py backend/tests/test_training_log_write.py
git commit -m "feat(coach): add append_training_log and append_body_metric with 200-entry cap"
```

---

### Task 4: profile_store.py — memory facts extraction

**Files:**
- Modify: `backend/packages/harness/deerflow/domain/coach/profile_store.py`
- Test: `backend/tests/test_coach_memory_facts.py`

- [ ] **Step 1: Write failing tests for extract_training_facts and extract_body_facts**

```python
# backend/tests/test_coach_memory_facts.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_coach_memory_facts.py -v`
Expected: FAIL — `extract_training_facts` and `extract_body_facts` not defined

- [ ] **Step 3: Implement extract_training_facts and extract_body_facts in profile_store.py**

Add after `append_body_metric`:

```python
def extract_training_facts(training_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract memory facts from training log entries using rule-based patterns."""
    if len(training_log) < 2:
        return []

    facts: list[dict[str, Any]] = []
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # Rule 1: Repeated focus_areas (consecutive 3)
    focus_counts: dict[str, int] = {}
    for entry in training_log[-5:]:
        for area in entry.get("focus_areas", []):
            if isinstance(area, str):
                focus_counts[area] = focus_counts.get(area, 0) + 1
    for area, count in focus_counts.items():
        if count >= 3:
            facts.append({
                "id": f"training_focus_{area}",
                "content": f"近期反复训练{area}",
                "category": "behavior",
                "confidence": 0.85,
                "createdAt": now_iso,
                "source": "training_log",
            })

    # Rule 2: Repeated issues (consecutive 3)
    issue_counts: dict[str, int] = {}
    for entry in training_log[-5:]:
        for issue in entry.get("issues", []):
            if isinstance(issue, str):
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
    for issue, count in issue_counts.items():
        if count >= 3:
            facts.append({
                "id": f"training_issue_{issue}",
                "content": f"{issue}问题近期持续存在",
                "category": "knowledge",
                "confidence": 0.80,
                "createdAt": now_iso,
                "source": "training_log",
            })

    # Rule 3: Repeated improvements (consecutive 2)
    improvement_counts: dict[str, int] = {}
    for entry in training_log[-3:]:
        for imp in entry.get("improvements", []):
            if isinstance(imp, str):
                improvement_counts[imp] = improvement_counts.get(imp, 0) + 1
    for imp, count in improvement_counts.items():
        if count >= 2:
            facts.append({
                "id": f"training_improvement_{imp}",
                "content": f"{imp}方面有持续进步",
                "category": "knowledge",
                "confidence": 0.75,
                "createdAt": now_iso,
                "source": "training_log",
            })

    logger.info("[coach] extract_training_facts: generated %d facts from training_log", len(facts))
    return facts


def extract_body_facts(body_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract memory facts from body metrics using rule-based patterns."""
    if not body_metrics:
        return []

    facts: list[dict[str, Any]] = []
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # Rule 1: Consecutive 3 high fatigue
    recent_fatigue = [e.get("fatigue_level", "") for e in body_metrics[-5:]]
    if len(recent_fatigue) >= 3 and all(f == "high" for f in recent_fatigue[-3:]):
        facts.append({
            "id": "body_fatigue_high",
            "content": "近期身体疲劳度偏高，需注意恢复",
            "category": "context",
            "confidence": 0.90,
            "createdAt": now_iso,
            "source": "body_metrics",
        })

    # Rule 2: avg_heart_rate rising trend
    hr_values = [
        e["avg_heart_rate"]
        for e in body_metrics[-5:]
        if isinstance(e.get("avg_heart_rate"), (int, float))
    ]
    if len(hr_values) >= 4:
        first_half = hr_values[: len(hr_values) // 2]
        second_half = hr_values[len(hr_values) // 2 :]
        if _mean(second_half) > _mean(first_half) * 1.03:
            facts.append({
                "id": "body_hr_rising",
                "content": "近期训练强度有上升趋势",
                "category": "context",
                "confidence": 0.80,
                "createdAt": now_iso,
                "source": "body_metrics",
            })

    # Rule 3: Single high calorie entry
    for entry in body_metrics[-1:]:
        cal = entry.get("calories_kcal")
        if isinstance(cal, (int, float)) and cal > 800:
            facts.append({
                "id": f"body_calories_{entry.get('date', 'unknown')}",
                "content": f"单次训练消耗较大（{int(cal)}kcal）",
                "category": "behavior",
                "confidence": 0.70,
                "createdAt": now_iso,
                "source": "body_metrics",
            })

    logger.info("[coach] extract_body_facts: generated %d facts from body_metrics", len(facts))
    return facts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_coach_memory_facts.py -v`
Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/domain/coach/profile_store.py backend/tests/test_coach_memory_facts.py
git commit -m "feat(coach): add rule-based memory fact extraction from training data"
```

---

### Task 5: BaseTool registration — query_training_log and get_body_metrics_trend

**Files:**
- Create: `backend/packages/harness/deerflow/tools/builtins/training_tools.py`
- Modify: `backend/packages/harness/deerflow/tools/tools.py`
- Test: `backend/tests/test_training_basetools.py`

- [ ] **Step 1: Write failing tests for BaseTools**

```python
# backend/tests/test_training_basetools.py
"""Tests for training data BaseTools."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from deerflow.config.paths import Paths


def _make_paths(base_dir: Path) -> Paths:
    return Paths(base_dir=base_dir)


def _write_profile(base_dir: Path, profile: dict) -> None:
    agent_dir = base_dir / "badminton-coach"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "coach_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def test_query_training_log_tool_exists():
    from deerflow.tools.builtins.training_tools import query_training_log
    assert query_training_log.name == "query_training_log"


def test_get_body_metrics_trend_tool_exists():
    from deerflow.tools.builtins.training_tools import get_body_metrics_trend_tool
    assert get_body_metrics_trend_tool.name == "get_body_metrics_trend"


def test_query_training_log_returns_summary(tmp_path: Path):
    profile = {
        "training_log": [
            {"date": "2026-05-19", "session_type": "match", "summary": "双打", "focus_areas": ["反手"], "issues": ["反手失误"], "improvements": []},
            {"date": "2026-05-21", "session_type": "training", "summary": "步法", "focus_areas": ["步法"], "issues": [], "improvements": ["步法有进步"]},
        ]
    }
    _write_profile(tmp_path, profile)

    from deerflow.tools.builtins.training_tools import query_training_log

    with patch("deerflow.domain.coach.training_data.get_paths", return_value=_make_paths(tmp_path)):
        result = query_training_log.invoke({"query": "反手", "n": 5})

    assert "反手" in result
    assert not result.startswith("数据不足")


def test_query_training_log_degrades(tmp_path: Path):
    _write_profile(tmp_path, {"training_log": []})

    from deerflow.tools.builtins.training_tools import query_training_log

    with patch("deerflow.domain.coach.training_data.get_paths", return_value=_make_paths(tmp_path)):
        result = query_training_log.invoke({"query": "反手", "n": 5})

    assert "数据不足" in result


def test_get_body_metrics_trend_tool_returns_summary(tmp_path: Path):
    profile = {
        "body_metrics": [
            {"date": "2026-05-19", "avg_heart_rate": 140, "fatigue_level": "low"},
            {"date": "2026-05-21", "avg_heart_rate": 150, "fatigue_level": "medium"},
        ]
    }
    _write_profile(tmp_path, profile)

    from deerflow.tools.builtins.training_tools import get_body_metrics_trend_tool

    with patch("deerflow.domain.coach.training_data.get_paths", return_value=_make_paths(tmp_path)):
        result = get_body_metrics_trend_tool.invoke({"days": 14})

    assert "心率" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_training_basetools.py -v`
Expected: FAIL — module `deerflow.tools.builtins.training_tools` does not exist

- [ ] **Step 3: Create training_tools.py**

```python
# backend/packages/harness/deerflow/tools/builtins/training_tools.py
"""LLM-callable BaseTools for training log and body metrics queries."""

from __future__ import annotations

import logging
from typing import Any

from langchain.tools import tool

logger = logging.getLogger(__name__)


@tool("query_training_log", parse_docstring=True)
def query_training_log(query: str, n: int = 5, session_type: str | None = None) -> str:
    """Query the user's badminton training log with a free-form question.

    Use this when the user asks about their recent training history,
    performance patterns, or wants a summary of past sessions.

    Args:
        query: Free-form question about training (e.g. "最近反手表现怎么样").
        n: Number of recent entries to retrieve (default 5).
        session_type: Optional filter: "match", "training", or "drill".
    """
    logger.info('[coach] query_training_log tool invoked: query="%s" n=%d', query, n)

    from deerflow.domain.coach.training_data import get_recent_training_log

    ctx = get_recent_training_log(n, session_type=session_type)
    if ctx.degraded:
        return f"数据不足，无法回答：{ctx.degrade_reason}"

    lines = [f"最近 {len(ctx.entries)} 条训练记录："]
    for entry in ctx.entries:
        date = entry.get("date", "?")
        summary = entry.get("summary", "")
        focus = ", ".join(entry.get("focus_areas", []))
        issues = ", ".join(entry.get("issues", []))
        parts = [f"[{date}]"]
        if summary:
            parts.append(summary)
        if focus:
            parts.append(f"训练重点：{focus}")
        if issues:
            parts.append(f"问题：{issues}")
        lines.append(" | ".join(parts))

    return "\n".join(lines)


@tool("get_body_metrics_trend", parse_docstring=True)
def get_body_metrics_trend_tool(days: int = 14, metric: str | None = None) -> str:
    """Get the user's body metrics trend analysis (heart rate, fatigue, training load).

    Use this when the user asks about their physical condition trends,
    recovery patterns, or training intensity changes over time.

    Args:
        days: Number of days to analyze (default 14).
        metric: Optional focus: "heart_rate", "training_load", "recovery", or None for all.
    """
    logger.info("[coach] get_body_metrics_trend tool invoked: days=%d metric=%s", days, metric)

    from deerflow.domain.coach.training_data import get_body_metrics_trend

    ctx = get_body_metrics_trend(days)
    if ctx.degraded:
        return f"数据不足，无法进行趋势分析：{ctx.degrade_reason}"

    summary = ctx.trend_summary
    lines = [f"最近 {days} 天身体指标趋势："]

    if not metric or metric == "heart_rate":
        hr_trend = summary.get("avg_heart_rate_trend", "未知")
        hr_mean = summary.get("avg_heart_rate_mean", "?")
        lines.append(f"- 平均心率趋势：{hr_trend}（均值 {hr_mean} bpm）")

    if not metric or metric == "training_load":
        load_trend = summary.get("training_load_trend", "未知")
        load_mean = summary.get("training_load_mean", "?")
        lines.append(f"- 训练负荷趋势：{load_trend}（均值 {load_mean}）")

    if not metric or metric == "recovery":
        fatigue_ratio = summary.get("fatigue_high_ratio", "?")
        dominant = summary.get("dominant_fatigue", "未知")
        lines.append(f"- 高疲劳占比：{fatigue_ratio}，主要疲劳等级：{dominant}")

    return "\n".join(lines)
```

- [ ] **Step 4: Register in tools.py**

In `backend/packages/harness/deerflow/tools/tools.py`, add imports and to BUILTIN_TOOLS:

```python
from deerflow.tools.builtins.training_tools import query_training_log, get_body_metrics_trend_tool

BUILTIN_TOOLS = [
    present_file_tool,
    ask_clarification_tool,
    query_training_log,
    get_body_metrics_trend_tool,
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_training_basetools.py -v`
Expected: 5 tests PASS

- [ ] **Step 6: Run full test suite to check for regressions**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/packages/harness/deerflow/tools/builtins/training_tools.py backend/packages/harness/deerflow/tools/tools.py backend/tests/test_training_basetools.py
git commit -m "feat(coach): add query_training_log and get_body_metrics_trend BaseTools"
```

---

### Task 6: Router integration — prematch inject, postmatch write

**Files:**
- Modify: `backend/packages/harness/deerflow/domain/coach/router.py`
- Test: `backend/tests/test_coach_single_intent_router.py` (extend)

- [ ] **Step 1: Add failing tests for router data injection**

Append to `backend/tests/test_coach_single_intent_router.py`:

```python
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

    with patch("deerflow.domain.coach.router.get_paths", return_value=_make_paths(tmp_path)):
        result = route_single_intent("今晚打双打，赛前怎么热身？", memory_data={"facts": []})

    assert result.route == "prematch"
    assert "recent_training" in result.payload
    assert "body_trend" in result.payload


def test_route_prematch_degrades_gracefully(tmp_path: Path):
    with patch("deerflow.domain.coach.router.get_paths", return_value=_make_paths(tmp_path)):
        result = route_single_intent("今晚打双打，赛前怎么热身？", memory_data={"facts": []})

    assert result.route == "prematch"
    assert result.payload.get("recent_training_degraded") is True


def test_route_postmatch_writes_training_log(tmp_path: Path):
    with patch("deerflow.domain.coach.router.get_paths", return_value=_make_paths(tmp_path)):
        result = route_single_intent("今天打完后场步法还是慢，回位跟不上。", persist_postmatch=True)

    assert result.route == "postmatch"
    assert result.payload["training_log_persisted"] is True

    profile = _read_profile(tmp_path)
    assert len(profile.get("training_log", [])) >= 1
```

Note: `_write_profile` and `_read_profile` helpers need to be added at the top of the test file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_coach_single_intent_router.py::test_route_prematch_injects_training_data -v`
Expected: FAIL — `recent_training` not in payload

- [ ] **Step 3: Modify router.py to inject training data in prematch**

In `router.py`, add imports:

```python
import logging
from .training_data import get_recent_training_log, get_body_metrics_trend

logger = logging.getLogger(__name__)
```

In `_run_route_chain`, inside the `if route == "prematch":` block, before building the payload, add:

```python
    recent_training_ctx = get_recent_training_log(5, agent_name=agent_name)
    body_trend_ctx = get_body_metrics_trend(7, agent_name=agent_name)
```

Then add to both payload dicts (persist_postmatch=True and False branches):

```python
    "recent_training": recent_training_ctx.entries if not recent_training_ctx.degraded else [],
    "recent_training_degraded": recent_training_ctx.degraded,
    "body_trend": body_trend_ctx.trend_summary if not body_trend_ctx.degraded else {},
    "body_trend_degraded": body_trend_ctx.degraded,
```

- [ ] **Step 4: Modify router.py to write training log in postmatch**

In `_run_route_chain`, inside the `if route == "postmatch":` block, after `persist_postmatch` is True, add training_log write:

```python
    if persist_postmatch:
        persisted = process_postmatch_message(message, agent_name=agent_name)
        # Write training log entry
        try:
            log_entry = {
                "date": datetime.now(UTC).date().isoformat(),
                "session_type": "match" if any(w in message for w in ("打", "比赛", "对抗")) else "training",
                "summary": persisted.review.summary,
                "focus_areas": persisted.review.next_focus,
                "improvements": [imp.topic for imp in persisted.review.improvements],
                "issues": [obs.topic for obs in persisted.review.technical_observations],
                "source": "postmatch",
            }
            from .profile_store import append_training_log
            append_training_log(log_entry, agent_name=agent_name)
            payload["training_log_persisted"] = True
        except Exception as exc:
            logger.error("[coach] postmatch: training_log write failed — %s", exc, exc_info=True)
            payload["training_log_persisted"] = False
```

Also update the non-persisted branch to include `training_log_persisted: False`.

- [ ] **Step 5: Add logging to router.py**

Add `logger.info` at the start of each route block:

```python
logger.info(
    "[coach] prematch route: recent_training degraded=%s body_trend degraded=%s",
    recent_training_ctx.degraded,
    body_trend_ctx.degraded,
)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_coach_single_intent_router.py -v`
Expected: ALL PASS (existing + new tests)

- [ ] **Step 7: Commit**

```bash
git add backend/packages/harness/deerflow/domain/coach/router.py backend/tests/test_coach_single_intent_router.py
git commit -m "feat(coach): integrate training data into prematch/postmatch routes"
```

---

### Task 7: Router integration — health route body metric write + trend

**Files:**
- Modify: `backend/packages/harness/deerflow/domain/coach/router.py`
- Test: `backend/tests/test_coach_single_intent_router.py` (extend)

- [ ] **Step 1: Add failing test for health route body metric write**

Append to `backend/tests/test_coach_single_intent_router.py`:

```python
def test_route_health_writes_body_metric(tmp_path: Path):
    with patch("deerflow.domain.coach.router.get_paths", return_value=_make_paths(tmp_path)):
        result = route_single_intent(
            "昨晚睡眠 5小时18分钟 HRV 28，今天怎么恢复？",
            persist_postmatch=True,
        )

    assert result.route == "health"
    assert result.payload["body_metric_persisted"] is True

    profile = _read_profile(tmp_path)
    assert len(profile.get("body_metrics", [])) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_coach_single_intent_router.py::test_route_health_writes_body_metric -v`
Expected: FAIL — `body_metric_persisted` not in payload

- [ ] **Step 3: Modify health route in router.py**

In `_run_route_chain`, inside the `if route == "health":` block, after the existing persistence logic, add:

```python
    if persist_postmatch:
        # existing persist_health_observation call...
        
        # Write body metric entry
        try:
            metric_entry = {
                "date": datetime.now(UTC).date().isoformat(),
                "fatigue_level": advice.risk_level if advice.risk_level in {"low", "medium", "high"} else "medium",
                "source": "health_report",
            }
            # Extract metrics from observation if available
            if observation.observed_metrics:
                if "avg_hr" in observation.observed_metrics:
                    metric_entry["avg_heart_rate"] = observation.observed_metrics["avg_hr"]
                if "max_hr" in observation.observed_metrics:
                    metric_entry["max_heart_rate"] = observation.observed_metrics["max_hr"]
                if "training_load" in observation.observed_metrics:
                    metric_entry["training_load"] = observation.observed_metrics["training_load"]
                if "recovery_hours" in observation.observed_metrics:
                    metric_entry["recovery_hours"] = observation.observed_metrics["recovery_hours"]
                if "calories" in observation.observed_metrics:
                    metric_entry["calories_kcal"] = observation.observed_metrics["calories"]
                if "duration_min" in observation.observed_metrics:
                    metric_entry["duration_min"] = observation.observed_metrics["duration_min"]

            from .profile_store import append_body_metric
            append_body_metric(metric_entry, agent_name=agent_name)
            payload["body_metric_persisted"] = True
        except Exception as exc:
            logger.error("[coach] health: body_metric write failed — %s", exc, exc_info=True)
            payload["body_metric_persisted"] = False

        # Add body trend
        body_trend_ctx = get_body_metrics_trend(14, agent_name=agent_name)
        payload["body_trend"] = body_trend_ctx.trend_summary if not body_trend_ctx.degraded else {}
        payload["body_trend_degraded"] = body_trend_ctx.degraded
```

Also add `body_metric_persisted: False` and `body_trend_degraded: True` to the non-persisted branch.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_coach_single_intent_router.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/domain/coach/router.py
git commit -m "feat(coach): integrate body metrics into health route with trend analysis"
```

---

### Task 8: Response renderer — handle degraded training data

**Files:**
- Modify: `backend/packages/harness/deerflow/domain/coach/response_renderer.py`

- [ ] **Step 1: Add degraded-aware rendering to prematch**

In `_render_prematch`, after the existing recall_line, add:

```python
    recent_training = payload.get("recent_training")
    if isinstance(recent_training, list) and recent_training and not payload.get("recent_training_degraded"):
        lines.append(_render_training_context(recent_training, persona))
```

Add helper function:

```python
def _render_training_context(entries: list[dict[str, Any]], persona: CoachPersonaConfig) -> str:
    """Render recent training context into the prematch response."""
    if not entries:
        return ""

    focus_areas: list[str] = []
    for entry in entries[:3]:
        for area in entry.get("focus_areas", []):
            if isinstance(area, str) and area not in focus_areas:
                focus_areas.append(area)

    if not focus_areas:
        return ""

    if persona.tone == "strict":
        return f"看了一下你最近的训练记录，继续盯住：{', '.join(focus_areas[:3])}。"
    return f"翻了你最近的训练记录，重点还是在：{', '.join(focus_areas[:3])}。"
```

- [ ] **Step 2: Run existing renderer tests to check no regression**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/ -k "coach" -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/domain/coach/response_renderer.py
git commit -m "feat(coach): render recent training context in prematch responses"
```

---

### Task 9: __init__.py exports

**Files:**
- Modify: `backend/packages/harness/deerflow/domain/coach/__init__.py`

- [ ] **Step 1: Add exports for new types and functions**

Add imports:

```python
from .training_data import (
    BodyMetricsContext,
    TrainingLogContext,
    get_body_metrics_trend,
    get_recent_training_log,
)
```

Add to `__all__`:

```python
    "BodyMetricsContext",
    "TrainingLogContext",
    "append_training_log",
    "append_body_metric",
    "extract_training_facts",
    "extract_body_facts",
    "get_body_metrics_trend",
    "get_recent_training_log",
```

Also add `append_training_log`, `append_body_metric`, `extract_training_facts`, `extract_body_facts` imports from `.profile_store`.

- [ ] **Step 2: Run full test suite**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/domain/coach/__init__.py
git commit -m "feat(coach): export new training data types and functions"
```

---

### Task 10: End-to-end validation

- [ ] **Step 1: Run full test suite**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/ -v`
Expected: All tests PASS, no regressions

- [ ] **Step 2: Run lint**

Run: `cd backend && uv run ruff check packages/harness/deerflow/domain/coach/ packages/harness/deerflow/tools/`
Expected: No errors

- [ ] **Step 3: Final commit (if any lint fixes needed)**

---

## Spec Coverage Check

| Spec Requirement | Task |
|---|---|
| training_log[] schema in coach_profile | Task 3 (append_training_log) |
| body_metrics[] schema in coach_profile | Task 3 (append_body_metric) |
| 200 entry cap | Task 3 |
| get_recent_training_log(n, session_type?) | Task 1 |
| get_body_metrics_trend(days) | Task 1-2 |
| Degrade pattern (weather.py style) | Task 1 |
| query_training_log BaseTool | Task 5 |
| get_body_metrics_trend BaseTool | Task 5 |
| Prematch route data injection | Task 6 |
| Postmatch route training_log write | Task 6 |
| Health route body_metric write + trend | Task 7 |
| Response renderer degraded handling | Task 8 |
| extract_training_facts (rule-based) | Task 4 |
| extract_body_facts (rule-based) | Task 4 |
| Memory fact structure + dedup | Task 4 |
| Logging across all modules | Tasks 1, 3, 6, 7 |
| __init__.py exports | Task 9 |

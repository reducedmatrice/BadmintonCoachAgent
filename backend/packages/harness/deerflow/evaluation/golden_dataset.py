"""Golden dataset schema and generation helpers for coach evaluation."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

TARGET_SCENARIO_COUNTS = {
    "multi_turn": 150,
    "mixed_intent": 120,
    "health": 100,
    "safety": 80,
    "fallback": 50,
}

_SCENARIO_TEMPLATES: dict[str, list[str]] = {
    "multi_turn": [
        "延续上一轮，{message}",
        "接着刚才那条再往下问，{message}",
        "基于前面聊到的内容，{message}",
    ],
    "mixed_intent": [
        "{message}，顺便结合上次复盘一起看。",
        "{message}，另外把恢复风险也一起带上。",
        "{message}，再加一句如果我还想复盘应该怎么接。",
    ],
    "health": [
        "{message}，我还想知道明天能不能上强度。",
        "{message}，请顺手判断一下恢复风险。",
        "{message}，再补一句下一次训练强度建议。",
    ],
    "safety": [
        "{message}，如果疼痛继续加重该怎么处理？",
        "{message}，如果今晚还硬打会有什么风险？",
        "{message}，请优先告诉我需要避免什么。",
    ],
    "fallback": [
        "我这个情况你先帮我判断一下，{message}",
        "信息可能不全，但你先看看，{message}",
        "我没法说得太细，先按现在这句来，{message}",
    ],
}


def load_seed_cases(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Seed cases must be a JSON array")
    return [case for case in data if isinstance(case, dict)]


def build_golden_dataset(seed_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand seed cases into a 500-case labeled golden dataset."""
    if not seed_cases:
        raise ValueError("At least one seed case is required")

    categorized = _categorize_seed_cases(seed_cases)
    dataset: list[dict[str, Any]] = []
    for scenario_type, target_count in TARGET_SCENARIO_COUNTS.items():
        scenario_seeds = categorized.get(scenario_type) or seed_cases
        for index in range(target_count):
            seed = scenario_seeds[index % len(scenario_seeds)]
            dataset.append(_materialize_case(seed, scenario_type=scenario_type, variant_index=index))

    return dataset


def validate_golden_dataset(cases: list[dict[str, Any]]) -> None:
    """Validate required schema and scenario distribution."""
    if len(cases) != sum(TARGET_SCENARIO_COUNTS.values()):
        raise ValueError("Golden dataset must contain exactly 500 cases")

    required_fields = {
        "case_id",
        "source_type",
        "scenario_type",
        "message",
        "expected_primary_route",
        "expected_secondary_routes",
        "expected_execution_order",
        "expected_fallback",
        "expected_safety_level",
        "expected_memory_use",
        "notes",
    }
    scenario_counts: Counter[str] = Counter()
    for case in cases:
        missing = sorted(field for field in required_fields if field not in case)
        if missing:
            raise ValueError(f"Case missing required fields: {missing}")
        scenario_type = case["scenario_type"]
        if scenario_type not in TARGET_SCENARIO_COUNTS:
            raise ValueError(f"Unsupported scenario_type: {scenario_type}")
        if not isinstance(case["expected_secondary_routes"], list):
            raise ValueError("expected_secondary_routes must be a list")
        if not isinstance(case["expected_execution_order"], list):
            raise ValueError("expected_execution_order must be a list")
        scenario_counts[scenario_type] += 1

    for scenario_type, expected_count in TARGET_SCENARIO_COUNTS.items():
        if scenario_counts[scenario_type] != expected_count:
            raise ValueError(f"scenario_type {scenario_type} must contain {expected_count} cases")


def write_golden_dataset(cases: list[dict[str, Any]], path: str | Path) -> None:
    Path(path).write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summarize_golden_dataset(cases: list[dict[str, Any]]) -> dict[str, Any]:
    scenario_counts = Counter(str(case.get("scenario_type", "")) for case in cases)
    source_counts = Counter(str(case.get("source_type", "")) for case in cases)
    return {
        "total_cases": len(cases),
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
    }


def _categorize_seed_cases(seed_cases: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    categorized: dict[str, list[dict[str, Any]]] = {key: [] for key in TARGET_SCENARIO_COUNTS}
    for case in seed_cases:
        scenario_type = _infer_scenario_type(case)
        categorized.setdefault(scenario_type, []).append(case)
    return categorized


def _infer_scenario_type(case: dict[str, Any]) -> str:
    expected_secondary = case.get("expected_secondary_intents")
    if isinstance(expected_secondary, list) and expected_secondary:
        return "mixed_intent"
    if case.get("image_summary"):
        return "health"
    if case.get("persona_expectations") or case.get("writeback_expectations"):
        return "multi_turn"
    route = str(case.get("expected_route", ""))
    message = str(case.get("message", ""))
    if route == "health" or any(keyword in message for keyword in ("疼", "痛", "恢复", "HRV", "睡眠")):
        return "health"
    if any(keyword in message for keyword in ("风险", "避免", "加重")):
        return "safety"
    if len(message) < 16 or "提醒" in message:
        return "fallback"
    return "multi_turn"


def _materialize_case(seed: dict[str, Any], *, scenario_type: str, variant_index: int) -> dict[str, Any]:
    primary_route = str(seed.get("expected_primary_intent") or seed.get("expected_route") or "fallback")
    secondary_routes = _normalize_routes(seed.get("expected_secondary_intents"))
    execution_order = _normalize_routes(seed.get("expected_execution_order")) or [primary_route, *secondary_routes]
    expected_fallback = scenario_type == "fallback" or primary_route == "fallback"
    expected_safety_level = _infer_safety_level(seed, scenario_type=scenario_type)
    expected_memory_use = bool(
        seed.get("coach_profile") or seed.get("weather") or seed.get("writeback_expectations") or primary_route == "postmatch"
    )
    template = _SCENARIO_TEMPLATES[scenario_type][variant_index % len(_SCENARIO_TEMPLATES[scenario_type])]
    source_type = _infer_source_type(seed)

    case = {
        "case_id": f"{scenario_type}-{variant_index + 1:03d}",
        "source_case_id": str(seed.get("id", "")),
        "source_type": source_type,
        "scenario_type": scenario_type,
        "message": template.format(message=str(seed.get("message", "")).strip()),
        "expected_primary_route": primary_route if not expected_fallback else "fallback",
        "expected_secondary_routes": [] if expected_fallback else secondary_routes,
        "expected_execution_order": ["fallback"] if expected_fallback else execution_order,
        "expected_fallback": expected_fallback,
        "expected_safety_level": expected_safety_level,
        "expected_memory_use": expected_memory_use,
        "notes": _build_notes(seed, scenario_type=scenario_type, source_type=source_type),
    }
    return case


def _normalize_routes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _infer_safety_level(seed: dict[str, Any], *, scenario_type: str) -> str:
    if scenario_type == "safety":
        return "high"
    route = str(seed.get("expected_route", ""))
    if route == "health":
        return "high"
    return "medium" if scenario_type in {"mixed_intent", "fallback"} else "low"


def _infer_source_type(seed: dict[str, Any]) -> str:
    if seed.get("writeback_expectations"):
        return "memory_log"
    if seed.get("image_summary"):
        return "gateway_log"
    if seed.get("coach_profile") or seed.get("weather"):
        return "eval_case"
    return "synthetic_boundary"


def _build_notes(seed: dict[str, Any], *, scenario_type: str, source_type: str) -> str:
    parts = [
        f"seed={seed.get('id', 'unknown')}",
        f"scenario={scenario_type}",
        f"source={source_type}",
    ]
    if seed.get("expected_secondary_intents"):
        parts.append("mixed-intent-seed")
    if seed.get("writeback_expectations"):
        parts.append("writeback-seed")
    return "; ".join(parts)

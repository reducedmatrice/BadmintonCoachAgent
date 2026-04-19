import json
from pathlib import Path

from generate_dataset import (
    build_fallback,
    build_health,
    build_mixed,
    build_overrides,
    build_postmatch,
    build_prematch,
    dedupe,
    make_output,
)


INSTRUCTIONS_V2 = [
    "你是羽毛球教练 Agent 的路由分类器。只允许输出一个 JSON object，禁止输出 markdown 代码块，禁止输出额外字段。字段名必须严格为 primary_intent、secondary_intents、slots、missing_slots、risk_level、confidence、needs_clarification、clarification_reason。",
    "这是严格的结构化分类任务。请仅返回合法 JSON，不要解释，不要添加 intent、task、request、sub_intent 等自创字段，必须只使用以下字段：primary_intent、secondary_intents、slots、missing_slots、risk_level、confidence、needs_clarification、clarification_reason。",
    "请按固定 schema 返回结果，只能输出一个 JSON 对象。不得使用代码块，不得增加额外键。允许的键只有：primary_intent、secondary_intents、slots、missing_slots、risk_level、confidence、needs_clarification、clarification_reason。",
]

OUT_DIR = Path(__file__).resolve().parent


def pack(items):
    result = []
    for idx, item in enumerate(items):
        result.append(
            {
                "instruction": INSTRUCTIONS_V2[idx % len(INSTRUCTIONS_V2)],
                "input": item["input"],
                "output": make_output(**item["payload"]),
            }
        )
    return result


def build_schema_guard_cases():
    cases = []
    examples = [
        (
            "今晚双打前帮我安排一下发接发，我最近脚下容易乱。",
            {
                "primary_intent": "prematch",
                "secondary_intents": [],
                "slots": {"session_goal": "发接发", "technical_focus": "脚下容易乱", "match_format": "doubles"},
                "missing_slots": [],
                "risk_level": "low",
                "confidence": 0.94,
                "needs_clarification": False,
                "clarification_reason": None,
            },
        ),
        (
            "今天打完最后两局明显掉速，帮我复盘一下。",
            {
                "primary_intent": "postmatch",
                "secondary_intents": [],
                "slots": {"review_text": "最后两局明显掉速"},
                "missing_slots": [],
                "risk_level": "low",
                "confidence": 0.95,
                "needs_clarification": False,
                "clarification_reason": None,
            },
        ),
        (
            "我现在膝盖刺痛，今晚还要不要打？",
            {
                "primary_intent": "health",
                "secondary_intents": ["prematch"],
                "slots": {"health_signal": "膝盖刺痛", "session_goal": "今晚还要不要打"},
                "missing_slots": [],
                "risk_level": "high",
                "confidence": 0.98,
                "needs_clarification": False,
                "clarification_reason": None,
            },
        ),
        (
            "帮我看看。",
            {
                "primary_intent": "fallback",
                "secondary_intents": [],
                "slots": {},
                "missing_slots": [],
                "risk_level": "low",
                "confidence": 0.18,
                "needs_clarification": True,
                "clarification_reason": "no_stable_intent_detected",
            },
        ),
    ]
    prefixes = ["", "@coach ", "我先问下，", "别解释，", "严格按字段返回，"]
    suffixes = ["", " 只给JSON。", " 不要额外字段。", " 不要代码块。"]
    for text, payload in examples:
        for prefix in prefixes:
            for suffix in suffixes:
                cases.append({"input": f"{prefix}{text}{suffix}", "payload": payload})
    return cases


def main():
    prematch = dedupe(build_prematch())
    postmatch = dedupe(build_postmatch())
    health = dedupe(build_health())
    mixed = dedupe(build_mixed())
    overrides = dedupe(build_overrides())
    fallback = dedupe(build_fallback())
    schema_guard = dedupe(build_schema_guard_cases())

    def take_unique(pool, target):
        out = []
        seen = set()
        for item in pool:
            if item["input"] in seen:
                continue
            seen.add(item["input"])
            out.append(item)
            if len(out) == target:
                return out
        raise ValueError(f"not enough unique items, need {target}, got {len(out)}")

    train_pool = (
        prematch[:120]
        + postmatch[:100]
        + health[:80]
        + mixed[:70]
        + overrides[:36]
        + fallback[:120]
        + schema_guard[:60]
    )
    val_pool = (
        prematch[120:180]
        + postmatch[100:160]
        + health[80:120]
        + mixed[70:94]
        + overrides[36:36]
        + fallback[120:220]
        + schema_guard[60:120]
    )
    test_pool = (
        prematch[180:240]
        + postmatch[160:220]
        + health[120:160]
        + mixed[94:118]
        + overrides[0:36]
        + fallback[220:320]
        + schema_guard[120:180]
    )

    train_raw = take_unique(train_pool, 300)
    val_raw = take_unique(val_pool, 60)
    test_raw = take_unique(test_pool, 60)

    train = pack(dedupe(train_raw))
    validation = pack(dedupe(val_raw))
    test = pack(dedupe(test_raw))

    assert len(train) == 300, len(train)
    assert len(validation) == 60, len(validation)
    assert len(test) == 60, len(test)

    all_inputs = [item["input"] for item in train + validation + test]
    assert len(all_inputs) == len(set(all_inputs)), "duplicate inputs detected across splits"

    (OUT_DIR / "train_v2.json").write_text(json.dumps(train, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "validation_v2.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "test_v2.json").write_text(json.dumps(test, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("generated_v2", len(train), len(validation), len(test))


if __name__ == "__main__":
    main()

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


INSTRUCTIONS_V3 = [
    "你是羽毛球教练 Agent 的结构化路由分类器。只允许输出一个 JSON object，不允许 markdown 代码块，不允许额外字段。primary_intent 只能从 prematch、postmatch、health、fallback 中选择；risk_level 只能是 low、medium、high；needs_clarification 只能是 true 或 false；confidence 必须是 0 到 1 的数字。",
    "请严格按固定 schema 返回。只能使用这些字段：primary_intent、secondary_intents、slots、missing_slots、risk_level、confidence、needs_clarification、clarification_reason。slots 只允许使用 session_goal、technical_focus、match_format、review_text、health_signal、time_context 这几个 key。",
    "这是枚举值受限的结构化分类任务。禁止输出 intent、task、request、sub_intent、训练类型、问题、运动类型 等字段或字段值。只返回一个合法 JSON 对象，并确保字段值使用英文枚举而不是中文描述。",
]

OUT_DIR = Path(__file__).resolve().parent

ALLOWED_SLOT_KEYS = [
    "session_goal",
    "technical_focus",
    "match_format",
    "review_text",
    "health_signal",
    "time_context",
]


def pack(items):
    result = []
    for idx, item in enumerate(items):
        result.append(
            {
                "instruction": INSTRUCTIONS_V3[idx % len(INSTRUCTIONS_V3)],
                "input": item["input"],
                "output": make_output(**item["payload"]),
            }
        )
    return result


def build_enum_guard_cases():
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
    suffixes = [
        " 只允许英文枚举值。",
        " risk_level 不允许写成中文。",
        " confidence 必须是小数，不允许写高、中、低。",
        " slots 里的 key 必须使用固定英文键名。",
    ]
    prefixes = ["", "严格按值域返回，", "@coach ", "不要发挥，", "再强调一次，"]
    for text, payload in examples:
        for prefix in prefixes:
            for suffix in suffixes:
                cases.append({"input": f"{prefix}{text}{suffix}", "payload": payload})
    return cases


def build_slot_guard_cases():
    items = []
    slot_examples = [
        ("今晚单打前帮我安排一下步伐，我最近第一步慢。", {"session_goal": "步伐", "technical_focus": "第一步慢", "match_format": "singles"}, "prematch"),
        ("今晚双打前帮我安排一下前后场转换，我最近后场回位慢。", {"session_goal": "前后场转换", "technical_focus": "后场回位慢", "match_format": "doubles"}, "prematch"),
        ("今天打完最后两局明显掉速，帮我复盘一下。", {"review_text": "最后两局明显掉速"}, "postmatch"),
        ("我这两天 HRV 有点低，明天还能上强度吗？", {"health_signal": "HRV有点低", "time_context": "明天"}, "health"),
    ]
    variants = [
        "slots 里不要出现训练类型、问题、运动类型这类中文 key。",
        f"slots 只允许这些 key：{', '.join(ALLOWED_SLOT_KEYS)}。",
        "请确保 slots 的 key 固定，不允许自由发明。",
    ]
    for text, slots, primary in slot_examples:
        for variant in variants:
            payload = {
                "primary_intent": primary,
                "secondary_intents": [],
                "slots": slots,
                "missing_slots": [],
                "risk_level": "low" if primary != "health" else "medium",
                "confidence": 0.93,
                "needs_clarification": False,
                "clarification_reason": None,
            }
            items.append({"input": f"{text} {variant}", "payload": payload})
    return items


def main():
    prematch = dedupe(build_prematch())
    postmatch = dedupe(build_postmatch())
    health = dedupe(build_health())
    mixed = dedupe(build_mixed())
    overrides = dedupe(build_overrides())
    fallback = dedupe(build_fallback())
    enum_guard = dedupe(build_enum_guard_cases())
    slot_guard = dedupe(build_slot_guard_cases())

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
        prematch[:100]
        + postmatch[:80]
        + health[:70]
        + mixed[:70]
        + overrides[:36]
        + fallback[:90]
        + enum_guard[:80]
        + slot_guard[:40]
    )
    val_pool = (
        prematch[100:150]
        + postmatch[80:130]
        + health[70:110]
        + mixed[70:94]
        + fallback[90:150]
        + enum_guard[80:120]
        + slot_guard[40:60]
    )
    test_pool = (
        prematch[150:200]
        + postmatch[130:180]
        + health[110:150]
        + mixed[94:118]
        + overrides[0:24]
        + fallback[150:210]
        + enum_guard[120:160]
        + slot_guard[60:80]
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

    (OUT_DIR / "train_v3.json").write_text(json.dumps(train, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "validation_v3.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "test_v3.json").write_text(json.dumps(test, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("generated_v3", len(train), len(validation), len(test))


if __name__ == "__main__":
    main()

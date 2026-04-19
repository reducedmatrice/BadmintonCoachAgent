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


OUT_DIR = Path(__file__).resolve().parent

ALLOWED_SLOT_KEYS = [
    "session_goal",
    "technical_focus",
    "match_format",
    "review_text",
    "health_signal",
    "time_context",
]

INSTRUCTIONS_V4 = [
    "你是羽毛球教练 Agent 的结构化路由分类器。只允许输出一个 JSON object，不允许 markdown 代码块，不允许解释，不允许额外字段。primary_intent 只能从 prematch、postmatch、health、fallback 中选择；risk_level 只能从 low、medium、high 中选择；needs_clarification 只能是 true 或 false；confidence 必须是 0 到 1 的数字。",
    "请严格按固定 schema 返回。只能使用这些字段：primary_intent、secondary_intents、slots、missing_slots、risk_level、confidence、needs_clarification、clarification_reason。slots 只允许使用 session_goal、technical_focus、match_format、review_text、health_signal、time_context 这几个 key。",
    "这是枚举值受限的结构化分类任务。禁止输出中文枚举值，禁止输出 intent、task、request、sub_intent、训练类型、问题、运动类型 等自由字段。只返回一个合法 JSON 对象。",
    "不要发挥，不要补建议，不要写代码块。你的任务不是回答用户问题，而是把用户输入映射到固定 schema，并且字段值必须落在允许的英文枚举范围内。",
]


def pack(items):
    result = []
    for idx, item in enumerate(items):
        result.append(
            {
                "instruction": INSTRUCTIONS_V4[idx % len(INSTRUCTIONS_V4)],
                "input": item["input"],
                "output": make_output(**item["payload"]),
            }
        )
    return result


def build_enum_guard_cases():
    cases = []
    examples = [
        (
            "今晚单打前帮我安排一下热身，我最近第一步慢。",
            {
                "primary_intent": "prematch",
                "secondary_intents": [],
                "slots": {"session_goal": "热身", "technical_focus": "第一步慢", "match_format": "singles"},
                "missing_slots": [],
                "risk_level": "low",
                "confidence": 0.92,
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
                "confidence": 0.12,
                "needs_clarification": True,
                "clarification_reason": "no_stable_intent_detected",
            },
        ),
    ]
    prefixes = [
        "",
        "@coach ",
        "不要发挥，",
        "严格按值域返回，",
        "只做路由分类，",
        "不要写建议，",
    ]
    suffixes = [
        " 只允许英文枚举值。",
        " risk_level 不允许写成中文。",
        " confidence 必须是小数，不允许写高、中、低。",
        " needs_clarification 只能返回 true 或 false。",
        " 不允许输出 markdown 代码块。",
    ]
    for text, payload in examples:
        for prefix in prefixes:
            for suffix in suffixes:
                cases.append({"input": f"{prefix}{text}{suffix}", "payload": payload})
    return cases


def build_slot_guard_cases():
    items = []
    slot_examples = [
        (
            "今晚双打前帮我安排一下发接发，我最近脚下容易乱。",
            {"session_goal": "发接发", "technical_focus": "脚下容易乱", "match_format": "doubles"},
            "prematch",
            "low",
        ),
        (
            "今天打完被压后场顶不住，帮我复盘一下。",
            {"review_text": "被压后场顶不住"},
            "postmatch",
            "low",
        ),
        (
            "我这两天 HRV 有点低，明天还能上强度吗？",
            {"health_signal": "HRV有点低", "time_context": "明天"},
            "health",
            "medium",
        ),
        (
            "今晚训练前想顾一下启动，不过我昨晚睡眠不够。",
            {"session_goal": "启动", "health_signal": "昨晚睡眠不够"},
            "prematch",
            "medium",
        ),
    ]
    variants = [
        "slots 里不要出现训练类型、问题、运动类型这类中文 key。",
        f"slots 只允许这些 key：{', '.join(ALLOWED_SLOT_KEYS)}。",
        "请确保 slots 的 key 固定，不允许自由发明。",
        "如果没有对应信息，就不要乱造 slot key。",
    ]
    for text, slots, primary, risk in slot_examples:
        for variant in variants:
            payload = {
                "primary_intent": primary,
                "secondary_intents": ["health"] if primary == "prematch" and "health_signal" in slots else [],
                "slots": slots,
                "missing_slots": [],
                "risk_level": risk,
                "confidence": 0.93,
                "needs_clarification": False,
                "clarification_reason": None,
            }
            items.append({"input": f"{text} {variant}", "payload": payload})
    return items


def build_correction_cases():
    items = []
    examples = [
        (
            "今晚单打前帮我安排一下热身，我最近后场回位慢。",
            {
                "primary_intent": "prematch",
                "secondary_intents": [],
                "slots": {"session_goal": "热身", "technical_focus": "后场回位慢", "match_format": "singles"},
                "missing_slots": [],
                "risk_level": "low",
                "confidence": 0.94,
                "needs_clarification": False,
                "clarification_reason": None,
            },
        ),
        (
            "今天打完第一步还是慢，帮我复盘问题。",
            {
                "primary_intent": "postmatch",
                "secondary_intents": [],
                "slots": {"review_text": "第一步还是慢"},
                "missing_slots": [],
                "risk_level": "low",
                "confidence": 0.91,
                "needs_clarification": False,
                "clarification_reason": None,
            },
        ),
        (
            "膝盖有点刺痛，但我今晚还想上场。",
            {
                "primary_intent": "health",
                "secondary_intents": ["prematch"],
                "slots": {"health_signal": "膝盖有点刺痛", "session_goal": "今晚还想上场"},
                "missing_slots": [],
                "risk_level": "high",
                "confidence": 0.97,
                "needs_clarification": False,
                "clarification_reason": None,
            },
        ),
        (
            "这个情况你看呢。",
            {
                "primary_intent": "fallback",
                "secondary_intents": [],
                "slots": {},
                "missing_slots": [],
                "risk_level": "low",
                "confidence": 0.15,
                "needs_clarification": True,
                "clarification_reason": "no_stable_intent_detected",
            },
        ),
    ]
    bad_forms = [
        "不要输出像“安排热身活动”“运动指导”“低”“高”这种自然语言字段值。",
        "不要把 low 写成低，不要把 confidence 写成高。",
        "不要输出 ```json 代码块。",
        "不要自创 warmUpActivity、task、request 之类字段。",
        "如果你想输出中文描述，改成固定英文枚举值。",
    ]
    for text, payload in examples:
        for bad_form in bad_forms:
            items.append({"input": f"{text} {bad_form}", "payload": payload})
    return items


def build_clarification_boundary_cases():
    items = []
    ambiguous = [
        "我最近不太对，今晚该怎么弄？",
        "这个状态行不行？",
        "你先判断一下我现在这种情况。",
        "我有点怪，你看下。",
        "今天这样要注意什么？",
    ]
    weak_health = [
        "今天有点累",
        "昨晚睡得一般",
        "感觉状态一般",
    ]
    specific_health = [
        ("我现在膝盖刺痛，今晚还能不能打？", "膝盖刺痛", "high", False),
        ("我昨晚只睡了 5 小时，今天还适合上强度吗？", "昨晚只睡了5小时", "medium", False),
        ("我小腿发紧，但今晚已经约了双打。", "小腿发紧", "medium", False),
    ]
    for text in ambiguous:
        items.append(
            {
                "input": text,
                "payload": {
                    "primary_intent": "fallback",
                    "secondary_intents": [],
                    "slots": {},
                    "missing_slots": [],
                    "risk_level": "low",
                    "confidence": 0.14,
                    "needs_clarification": True,
                    "clarification_reason": "no_stable_intent_detected",
                },
            }
        )
    for signal in weak_health:
        items.append(
            {
                "input": f"{signal}，今晚还能不能打？如果信息不够请走澄清。",
                "payload": {
                    "primary_intent": "health",
                    "secondary_intents": ["prematch"],
                    "slots": {"health_signal": signal, "session_goal": "今晚还能不能打"},
                    "missing_slots": [],
                    "risk_level": "medium",
                    "confidence": 0.56,
                    "needs_clarification": True,
                    "clarification_reason": "need_more_health_context",
                },
            }
        )
    for text, signal, risk, clarify in specific_health:
        items.append(
            {
                "input": text,
                "payload": {
                    "primary_intent": "health",
                    "secondary_intents": ["prematch"],
                    "slots": {"health_signal": signal, "session_goal": "今晚还能不能打" if "今晚" in text else "今天还适合上强度吗"},
                    "missing_slots": [],
                    "risk_level": risk,
                    "confidence": 0.94 if risk == "high" else 0.84,
                    "needs_clarification": clarify,
                    "clarification_reason": None if not clarify else "need_more_health_context",
                },
            }
        )
    return items


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


def main():
    prematch = dedupe(build_prematch())
    postmatch = dedupe(build_postmatch())
    health = dedupe(build_health())
    mixed = dedupe(build_mixed())
    overrides = dedupe(build_overrides())
    fallback = dedupe(build_fallback())
    enum_guard = dedupe(build_enum_guard_cases())
    slot_guard = dedupe(build_slot_guard_cases())
    correction = dedupe(build_correction_cases())
    clarify_boundary = dedupe(build_clarification_boundary_cases())

    train_pool = (
        prematch[:180]
        + postmatch[:110]
        + health[:100]
        + mixed[:40]
        + overrides[:20]
        + fallback[:230]
        + enum_guard[:100]
        + slot_guard[:16]
        + correction[:20]
        + clarify_boundary[:4]
    )
    val_pool = (
        prematch[180:240]
        + postmatch[110:140]
        + health[100:125]
        + mixed[40:50]
        + overrides[20:28]
        + fallback[230:287]
        + enum_guard[100:110]
        + clarify_boundary[4:8]
    )
    test_pool = (
        prematch[240:300]
        + postmatch[140:170]
        + health[125:150]
        + mixed[50:60]
        + overrides[28:36]
        + fallback[287:344]
        + enum_guard[110:120]
        + clarify_boundary[8:11]
    )

    train = pack(take_unique(train_pool, 819))
    validation = pack(take_unique(val_pool, 120))
    test = pack(take_unique(test_pool, 120))

    all_inputs = [item["input"] for item in train + validation + test]
    assert len(all_inputs) == len(set(all_inputs)), "duplicate inputs detected across splits"

    (OUT_DIR / "train_v4.json").write_text(json.dumps(train, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "validation_v4.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "test_v4.json").write_text(json.dumps(test, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("generated_v4", len(train), len(validation), len(test))


if __name__ == "__main__":
    main()

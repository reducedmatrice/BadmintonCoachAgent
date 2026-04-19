import json
from pathlib import Path

INSTRUCTIONS = [
    "请根据用户输入输出标准 JSON，只返回 JSON，不要解释。",
    "你是羽毛球教练 Agent 的结构化意图分类器。请识别意图并返回 JSON。",
    "这是一个路由分类任务。请基于用户输入返回结构化 JSON 结果。",
]

OUT_DIR = Path(__file__).resolve().parent


def make_output(
    primary_intent,
    secondary_intents,
    slots,
    risk_level,
    confidence,
    needs_clarification=False,
    clarification_reason=None,
    missing_slots=None,
):
    payload = {
        "primary_intent": primary_intent,
        "secondary_intents": secondary_intents,
        "slots": slots,
        "missing_slots": missing_slots or [],
        "risk_level": risk_level,
        "confidence": confidence,
        "needs_clarification": needs_clarification,
        "clarification_reason": clarification_reason,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def pack(items):
    result = []
    for idx, item in enumerate(items):
        result.append(
            {
                "instruction": INSTRUCTIONS[idx % len(INSTRUCTIONS)],
                "input": item["input"],
                "output": make_output(**item["payload"]),
            }
        )
    return result


def build_prematch():
    match_formats = ["双打", "单打", "对抗", "训练"]
    goals = [
        "热身",
        "接发",
        "步伐",
        "启动",
        "后场回位",
        "网前启动",
        "杀球衔接",
        "第一拍节奏",
        "发接发",
        "前后场转换",
    ]
    issues = [
        "第一步慢",
        "后场回位慢",
        "启动总慢半拍",
        "网前容易顶住",
        "反手准备不够快",
        "脚下容易乱",
        "后场高远球衔接差",
        "接发后衔接慢",
        "上来容易发紧",
        "节奏一快就散",
    ]
    frames = [
        "今晚{}前帮我安排一下{}，我最近{}。",
        "我今天准备打{}，赛前想重点顾一下{}，因为我总觉得{}。",
        "等会去打{}，上场前我该怎么准备{}？我最近{}。",
        "今天去{}，打前提醒我一下{}，这阵子我{}。",
        "@coach 今晚{}前给我一个{}建议，我现在的问题是{}。",
    ]
    items = []
    idx = 0
    for frame in frames:
        for match in match_formats:
            for goal in goals:
                for issue in issues:
                    text = frame.format(match, goal, issue)
                    match_slot = "doubles" if match == "双打" else "singles" if match == "单打" else None
                    slots = {"session_goal": goal, "technical_focus": issue}
                    if match_slot:
                        slots["match_format"] = match_slot
                    items.append(
                        {
                            "input": text,
                            "payload": {
                                "primary_intent": "prematch",
                                "secondary_intents": [],
                                "slots": slots,
                                "risk_level": "low",
                                "confidence": round(0.88 + (idx % 8) * 0.01, 2),
                            },
                        }
                    )
                    idx += 1
    return items


def build_postmatch():
    positives = [
        "反手稳了一点",
        "网前手感还行",
        "发接发还算在线",
        "前半段节奏还不错",
        "防守比之前沉得住",
        "平抽速度还可以",
        "落点比之前稳",
        "心态没那么急了",
    ]
    negatives = [
        "后场回位还是慢",
        "第一步还是慢",
        "后半段脚下乱了",
        "最后两局明显掉速",
        "高远球不到位",
        "被压后场时顶不住",
        "启动衔接还是断",
        "接发后容易站死",
        "网前起球质量一般",
        "体能后程掉得快",
    ]
    frames = [
        "刚打完，今天{}，但{}，帮我复盘一下。",
        "我今天打完的感觉是{}，不过{}，给我总结下次重点。",
        "今天打完球，{}，可{}，帮我回顾一下失误。",
        "刚结束，{}，但是{}，你帮我看看问题在哪。",
    ]
    items = []
    idx = 0
    for frame in frames:
        for pos in positives:
            for neg in negatives:
                text = frame.format(pos, neg)
                items.append(
                    {
                        "input": text,
                        "payload": {
                            "primary_intent": "postmatch",
                            "secondary_intents": [],
                            "slots": {"review_text": f"{pos}，但{neg}"},
                            "risk_level": "low",
                            "confidence": round(0.89 + (idx % 7) * 0.01, 2),
                        },
                    }
                )
                idx += 1
    return items


def build_health():
    signals = [
        "膝盖有点疼",
        "肩膀酸",
        "小腿发紧",
        "昨晚只睡了5小时",
        "HRV有点低",
        "今天特别疲劳",
        "静息心率偏高",
        "腰有点不舒服",
        "最高心率184",
        "恢复截图显示睡眠不够",
    ]
    asks = [
        "明天还能上强度吗？",
        "今天还适合打吗？",
        "这种情况是不是该收一点？",
        "我还要不要练？",
        "今晚能不能正常打？",
    ]
    frames = [
        "我这两天{}，{}",
        "帮我看下，我现在{}，{}",
        "今天{}，{}",
        "这是恢复信息：{}，{}",
    ]
    items = []
    idx = 0
    for frame in frames:
        for signal in signals:
            for ask in asks:
                text = frame.format(signal, ask)
                risk = "high" if "184" in signal else "medium"
                items.append(
                    {
                        "input": text,
                        "payload": {
                            "primary_intent": "health",
                            "secondary_intents": [],
                            "slots": {"health_signal": signal},
                            "risk_level": risk,
                            "confidence": round(0.87 + (idx % 9) * 0.01, 2),
                        },
                    }
                )
                idx += 1
    return items


def build_mixed():
    prematch_goals = ["热身", "步伐", "接发", "启动", "强度安排", "后场回位"]
    signals = ["肩膀酸", "膝盖不舒服", "昨晚恢复差", "小腿紧", "心率有点高", "睡眠不够"]
    post_negatives = ["最后两局掉速", "被压后场顶不住", "第一步还是慢", "脚下乱了"]
    items = []
    idx = 0
    for goal in prematch_goals:
        for signal in signals:
            text = f"今晚打球前我想先顾一下{goal}，不过我昨天{signal}，这种情况要怎么安排？"
            items.append(
                {
                    "input": text,
                    "payload": {
                        "primary_intent": "prematch",
                        "secondary_intents": ["health"],
                        "slots": {"session_goal": goal, "health_signal": signal},
                        "risk_level": "medium",
                        "confidence": round(0.87 + (idx % 6) * 0.01, 2),
                    },
                }
            )
            idx += 1
    for neg in post_negatives:
        for signal in signals:
            text = f"今天打完{neg}，而且我现在{signal}，帮我先看恢复再顺便复盘。"
            items.append(
                {
                    "input": text,
                    "payload": {
                        "primary_intent": "postmatch",
                        "secondary_intents": ["health"],
                        "slots": {"review_text": neg, "health_signal": signal},
                        "risk_level": "medium",
                        "confidence": round(0.86 + (idx % 6) * 0.01, 2),
                    },
                }
            )
            idx += 1
    return items


def build_overrides():
    injuries = ["膝盖刺痛", "肩膀刺痛", "刚扭到脚踝", "突然头晕", "小腿像拉伤了一样", "腰突然崩了一下"]
    goals = ["今晚还要打", "本来想练启动", "等会准备双打", "赛前热身还没做", "本来想加强后场", "还想正常上强度"]
    items = []
    idx = 0
    for goal in goals:
        for injury in injuries:
            text = f"{goal}，但我现在{injury}。"
            items.append(
                {
                    "input": text,
                    "payload": {
                        "primary_intent": "health",
                        "secondary_intents": ["prematch"],
                        "slots": {"session_goal": goal, "health_signal": injury},
                        "risk_level": "high",
                        "confidence": round(0.94 + (idx % 4) * 0.01, 2),
                    },
                }
            )
            idx += 1
    return items


def build_fallback():
    shorts = [
        "你好",
        "在吗",
        "帮我看看",
        "怎么看",
        "咋整",
        "这个怎么办",
        "我来了",
        "说说看",
        "看下",
        "有空吗",
    ]
    noisy = [
        "@coach 在不在",
        "a 帮我看下",
        "喂喂",
        "我这个有点那个",
        "先这样",
        "你先看看",
        "这个情况你看呢",
        "我先问一句",
        "这个咋说",
        "麻烦瞅一眼",
    ]
    ambiguous = [
        "今天有点怪，帮我看看。",
        "我感觉不太对，你说下。",
        "这个状态行不行？",
        "给我个建议呗。",
        "你先判断一下。",
        "我现在这样正常吗？",
        "这个该注意啥？",
        "我有点懵，帮我理一下。",
        "你先帮我看看情况。",
        "我也说不上来，你判断下。",
    ]
    items = []
    idx = 0
    for text in shorts + noisy + ambiguous:
        items.append(
            {
                "input": text,
                "payload": {
                    "primary_intent": "fallback",
                    "secondary_intents": [],
                    "slots": {},
                    "risk_level": "low",
                    "confidence": round(0.12 + (idx % 12) * 0.01, 2),
                    "needs_clarification": True,
                    "clarification_reason": "no_stable_intent_detected",
                },
            }
        )
        idx += 1
    suffixes = ["。", "啊", "呢", "呀", "呗", "哈"]
    prefixes = ["", "@coach ", "a ", "那个，", "就是 ", "我先问下，"]
    for base in ambiguous + noisy:
        for prefix in prefixes:
            for suffix in suffixes:
                text = f"{prefix}{base}{suffix}"
                items.append(
                    {
                        "input": text,
                        "payload": {
                            "primary_intent": "fallback",
                            "secondary_intents": [],
                            "slots": {},
                            "risk_level": "low",
                            "confidence": round(0.12 + (idx % 12) * 0.01, 2),
                            "needs_clarification": True,
                            "clarification_reason": "no_stable_intent_detected",
                        },
                    }
                )
                idx += 1
    return items


def dedupe(items):
    seen = set()
    out = []
    for item in items:
        if item["input"] in seen:
            continue
        seen.add(item["input"])
        out.append(item)
    return out


def main():
    prematch = build_prematch()
    postmatch = build_postmatch()
    health = build_health()
    mixed = build_mixed()
    overrides = build_overrides()
    fallback = build_fallback()

    train_raw = prematch[:85] + postmatch[:70] + health[:45] + mixed[:40] + overrides[:20] + fallback[:40]
    val_raw = prematch[85:100] + postmatch[70:80] + health[45:55] + mixed[40:50] + overrides[20:25] + fallback[40:50]
    test_raw = prematch[100:115] + postmatch[80:90] + health[55:65] + mixed[50:60] + overrides[25:30] + fallback[50:60]

    train = pack(dedupe(train_raw))
    validation = pack(dedupe(val_raw))
    test = pack(dedupe(test_raw))

    assert len(train) == 300, len(train)
    assert len(validation) == 60, len(validation)
    assert len(test) == 60, len(test)

    all_inputs = [item["input"] for item in train + validation + test]
    assert len(all_inputs) == len(set(all_inputs)), "duplicate inputs detected across splits"

    (OUT_DIR / "train.json").write_text(json.dumps(train, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "test.json").write_text(json.dumps(test, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("generated", len(train), len(validation), len(test))


if __name__ == "__main__":
    main()

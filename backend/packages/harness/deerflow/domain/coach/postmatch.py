"""Rule-based postmatch extraction for the badminton coach agent."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TechnicalObservation:
    topic: str
    finding: str
    severity: float
    evidence: str


@dataclass
class Improvement:
    topic: str
    evidence: str


@dataclass
class PostmatchReview:
    technical_observations: list[TechnicalObservation]
    improvements: list[Improvement]
    next_focus: list[str]
    emotional_notes: list[str]
    summary: str


_TOPIC_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("后场步法", ("后场", "回位", "后撤", "启动", "步法")),
    ("反手稳定性", ("反手",)),
    ("杀球衔接", ("杀球", "下压")),
    ("封网衔接", ("封网", "网前")),
    ("体能节奏", ("累", "体能", "脚下沉", "跟不上")),
]

_EMOTIONAL_PATTERNS = ("心态", "着急", "烦", "紧张", "郁闷", "崩", "急躁", "没信心")
_WEAKNESS_MARKERS = ("还是", "不够", "太慢", "跟不上", "不到位", "容易", "老是", "失误")
_IMPROVEMENT_MARKERS = ("有进步", "更稳", "更敢", "好了", "顺了", "改善", "提升")
_NEXT_FOCUS_MARKERS = ("下次重点", "下次", "接下来", "要练", "优先", "继续盯")


def extract_postmatch_review(message: str) -> PostmatchReview:
    """Extract structured observations from a postmatch recap."""
    sentences = _split_sentences(message)
    technical_observations: list[TechnicalObservation] = []
    improvements: list[Improvement] = []
    next_focus: list[str] = []
    emotional_notes: list[str] = []

    for sentence in sentences:
        if any(marker in sentence for marker in _EMOTIONAL_PATTERNS):
            emotional_notes.append(sentence)
        for clause in _split_clauses(sentence):
            topics = _infer_topics(clause)

            if any(marker in clause for marker in _IMPROVEMENT_MARKERS):
                topic = topics[0] if topics else "整体状态"
                improvements.append(Improvement(topic=topic, evidence=clause))

            if any(marker in clause for marker in _NEXT_FOCUS_MARKERS):
                extracted_focus = _extract_next_focus(clause, topics)
                next_focus.extend(extracted_focus)

            if _looks_like_technical_issue(clause):
                topic = topics[0] if topics else "技术执行"
                finding = _extract_finding(clause, topic)
                technical_observations.append(
                    TechnicalObservation(
                        topic=topic,
                        finding=finding,
                        severity=_score_severity(clause),
                        evidence=clause,
                    )
                )

    summary_parts: list[str] = []
    if technical_observations:
        summary_parts.append(f"识别到 {len(technical_observations)} 条技术问题")
    if improvements:
        summary_parts.append(f"{len(improvements)} 条进步点")
    if next_focus:
        summary_parts.append(f"下次重点：{'、'.join(_unique_keep_order(next_focus)[:3])}")
    if not summary_parts:
        summary_parts.append("本次复盘信息偏少，建议补充更具体的技术环节。")

    return PostmatchReview(
        technical_observations=_dedupe_observations(technical_observations),
        improvements=_dedupe_improvements(improvements),
        next_focus=_unique_keep_order(next_focus)[:3],
        emotional_notes=_unique_keep_order(emotional_notes),
        summary="；".join(summary_parts),
    )


def _split_sentences(message: str) -> list[str]:
    parts = re.split(r"[。！？!\n]+", message)
    return [part.strip(" ，,；;") for part in parts if part.strip(" ，,；;")]


def _split_clauses(sentence: str) -> list[str]:
    parts = re.split(r"[，,；;]|不过|但是|但", sentence)
    return [part.strip(" ，,；;") for part in parts if part.strip(" ，,；;")]


def _infer_topics(sentence: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    for topic, keywords in _TOPIC_PATTERNS:
        positions = [sentence.find(keyword) for keyword in keywords if keyword in sentence]
        if positions:
            matches.append((min(positions), topic))
    matches.sort(key=lambda item: item[0])
    return [topic for _, topic in matches]


def _looks_like_technical_issue(sentence: str) -> bool:
    if "没" in sentence and any(phrase in sentence for phrase in ("技术问题", "明显问题", "啥问题")):
        return False
    if any(marker in sentence for marker in _WEAKNESS_MARKERS):
        return True
    if "问题" in sentence or "弱项" in sentence:
        return True
    if ("慢" in sentence or "失误" in sentence) and not any(marker in sentence for marker in _EMOTIONAL_PATTERNS):
        return True
    return False


def _extract_finding(sentence: str, topic: str) -> str:
    cleaned = sentence
    for topic_name, keywords in _TOPIC_PATTERNS:
        if topic_name == topic:
            for keyword in keywords:
                cleaned = cleaned.replace(keyword, "", 1)
                break
    cleaned = cleaned.strip(" ，,；;")
    if not cleaned:
        return "执行不稳定"
    return cleaned


def _score_severity(sentence: str) -> float:
    if any(marker in sentence for marker in ("完全", "一直", "老是", "很慢", "特别")):
        return 0.85
    if any(marker in sentence for marker in ("还是", "不够", "跟不上", "失误")):
        return 0.7
    return 0.55


def _extract_next_focus(sentence: str, topics: list[str]) -> list[str]:
    results = list(topics)
    if "后场" in sentence and "后场步法" not in results:
        results.append("后场步法")
    if "反手" in sentence and "反手稳定性" not in results:
        results.append("反手稳定性")
    if "杀球" in sentence and "杀球衔接" not in results:
        results.append("杀球衔接")
    if not results:
        results.append(sentence)
    return results


def _dedupe_observations(items: list[TechnicalObservation]) -> list[TechnicalObservation]:
    seen: set[tuple[str, str]] = set()
    result: list[TechnicalObservation] = []
    for item in items:
        key = (item.topic, item.finding)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _dedupe_improvements(items: list[Improvement]) -> list[Improvement]:
    seen: set[tuple[str, str]] = set()
    result: list[Improvement] = []
    for item in items:
        key = (item.topic, item.evidence)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _unique_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

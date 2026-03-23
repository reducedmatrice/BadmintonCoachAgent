"""Health screenshot analysis helpers for the badminton coach agent."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class HealthImageObservation:
    screenshot_type: str
    observed_metrics: dict[str, float]
    observations: list[str]
    risk_level: str
    missing_data: list[str]


@dataclass
class HealthRecoveryAdvice:
    risk_level: str
    structured_observations: list[str]
    recovery_actions: list[str]
    next_session_intensity: str
    follow_up_question: str


def analyze_health_image_text(text: str) -> HealthImageObservation:
    """Convert OCR or vision notes from a health screenshot into structured observations."""
    normalized = " ".join(text.split())
    screenshot_type = _detect_screenshot_type(normalized)
    metrics = _extract_metrics(normalized)

    observations: list[str] = []
    missing_data: list[str] = []

    if screenshot_type == "heart_rate":
        max_hr = metrics.get("max_hr")
        avg_hr = metrics.get("avg_hr")
        duration = metrics.get("duration_min")
        if max_hr is not None and max_hr >= 180:
            observations.append("最高心率已经到高强度区间，这次负荷不轻。")
        if avg_hr is not None and avg_hr >= 160:
            observations.append("平均心率偏高，说明持续对抗时间不短。")
        if duration is not None and duration >= 90:
            observations.append("单次训练时长偏长，恢复压力会更明显。")
        if max_hr is None:
            missing_data.append("最高心率")
        if duration is None:
            missing_data.append("训练时长")

    elif screenshot_type == "sleep_recovery":
        sleep_min = metrics.get("sleep_min")
        hrv = metrics.get("hrv")
        resting_hr = metrics.get("resting_hr")
        if sleep_min is not None and sleep_min < 360:
            observations.append("睡眠时长不足 6 小时，恢复质量偏弱。")
        if hrv is not None and hrv < 35:
            observations.append("HRV 偏低，今天更像恢复日而不是冲强度日。")
        if resting_hr is not None and resting_hr >= 60:
            observations.append("静息心率不低，身体可能还没完全回到放松状态。")
        if sleep_min is None:
            missing_data.append("睡眠时长")
        if hrv is None:
            missing_data.append("HRV")

    elif screenshot_type == "training_load":
        load = metrics.get("training_load")
        recovery_hours = metrics.get("recovery_hours")
        duration = metrics.get("duration_min")
        if load is not None and load >= 150:
            observations.append("训练负荷偏高，说明上一节课刺激已经比较足。")
        if recovery_hours is not None and recovery_hours >= 24:
            observations.append("建议恢复时间超过 24 小时，不适合立刻顶第二次高强度。")
        if duration is not None and duration >= 100:
            observations.append("本次运动总时长较长，今天更应该优先做恢复。")
        if load is None:
            missing_data.append("训练负荷")
        if recovery_hours is None:
            missing_data.append("恢复时间")

    else:
        observations.append("截图里暂时没看到稳定可用的健康指标，只能给保守建议。")
        missing_data.extend(["截图类型", "关键指标"])

    risk_level = _infer_risk_level(screenshot_type, metrics)
    return HealthImageObservation(
        screenshot_type=screenshot_type,
        observed_metrics=metrics,
        observations=observations or ["截图已有基础信息，但不足以支持激进判断。"],
        risk_level=risk_level,
        missing_data=missing_data,
    )


def build_health_recovery_advice(observation: HealthImageObservation) -> HealthRecoveryAdvice:
    """Build conservative recovery advice from a structured screenshot observation."""
    actions = ["今天先补水、拉伸和简单放松，不要在疲劳没降下来时硬顶强度。"]
    follow_up_question = "你现在是单纯累、局部酸痛，还是有明显疼痛点？"

    if observation.risk_level == "high":
        actions.append("今晚以恢复为主，优先睡眠、轻松走动和下肢放松，不安排高强度多拍。")
        intensity = "下一次先按恢复或低强度处理，最多做轻技术和节奏练习。"
    elif observation.risk_level == "medium":
        actions.append("下一次可以练技术，但把总量压到平时的 60%-70%，不要连续加速对抗。")
        intensity = "下一次建议中低强度，重点练手感、步法节奏和落点控制。"
    else:
        actions.append("如果主观状态正常，下一次可回到常规训练，但前 15 分钟先观察身体反馈。")
        intensity = "下一次可常规推进，但仍建议先热身再抬强度。"

    if observation.screenshot_type == "sleep_recovery" and "HRV" in observation.missing_data:
        follow_up_question = "除了截图数据，你今天起床后的主观疲劳和腿部酸胀感怎么样？"
    elif observation.screenshot_type == "heart_rate":
        follow_up_question = "这次高心率主要出现在多拍对抗，还是冲刺追球阶段？"
    elif observation.screenshot_type == "training_load":
        follow_up_question = "这次高负荷之后，你现在更明显的是喘、腿沉，还是肩背紧？"

    return HealthRecoveryAdvice(
        risk_level=observation.risk_level,
        structured_observations=observation.observations,
        recovery_actions=actions,
        next_session_intensity=intensity,
        follow_up_question=follow_up_question,
    )


def _detect_screenshot_type(text: str) -> str:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("睡眠", "hrv", "静息心率", "resting heart rate")):
        return "sleep_recovery"
    if any(keyword in lowered for keyword in ("心率", "bpm", "平均心率", "最高心率")):
        return "heart_rate"
    if any(keyword in lowered for keyword in ("训练负荷", "恢复时间", "卡路里", "千卡", "calories")):
        return "training_load"
    return "unknown"


def _extract_metrics(text: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    max_hr = _extract_number(text, r"(?:最高心率|max(?:imum)? heart rate)[^0-9]{0,8}(\d{2,3})")
    avg_hr = _extract_number(text, r"(?:平均心率|avg(?:erage)? heart rate)[^0-9]{0,8}(\d{2,3})")
    resting_hr = _extract_number(text, r"(?:静息心率|resting heart rate)[^0-9]{0,8}(\d{2,3})")
    hrv = _extract_number(text, r"(?:hrv)[^0-9]{0,8}(\d{1,3})")
    training_load = _extract_number(text, r"(?:训练负荷|training load)[^0-9]{0,8}(\d{1,3})")
    recovery_hours = _extract_number(text, r"(?:恢复时间|recovery time)[^0-9]{0,8}(\d{1,3})")
    sleep_min = _extract_duration_minutes(text, label_pattern=r"(?:睡眠|sleep)")
    duration_min = _extract_duration_minutes(text, label_pattern=r"(?:时长|duration|运动|训练|羽毛球)")
    calories = _extract_number(text, r"(?:千卡|卡路里|calories)[^0-9]{0,8}(\d{2,4})")

    for key, value in (
        ("max_hr", max_hr),
        ("avg_hr", avg_hr),
        ("resting_hr", resting_hr),
        ("hrv", hrv),
        ("training_load", training_load),
        ("recovery_hours", recovery_hours),
        ("sleep_min", sleep_min),
        ("duration_min", duration_min),
        ("calories", calories),
    ):
        if value is not None:
            metrics[key] = value

    return metrics


def _infer_risk_level(screenshot_type: str, metrics: dict[str, float]) -> str:
    if screenshot_type == "heart_rate":
        if metrics.get("max_hr", 0) >= 180 or (
            metrics.get("avg_hr", 0) >= 160 and metrics.get("duration_min", 0) >= 75
        ):
            return "high"
        if metrics.get("avg_hr", 0) >= 145 or metrics.get("duration_min", 0) >= 60:
            return "medium"
        return "low"

    if screenshot_type == "sleep_recovery":
        if metrics.get("sleep_min", 999) < 330 or metrics.get("hrv", 999) < 30:
            return "high"
        if metrics.get("sleep_min", 999) < 420 or metrics.get("resting_hr", 0) >= 58:
            return "medium"
        return "low"

    if screenshot_type == "training_load":
        if metrics.get("training_load", 0) >= 160 or metrics.get("recovery_hours", 0) >= 30:
            return "high"
        if metrics.get("training_load", 0) >= 110 or metrics.get("duration_min", 0) >= 80:
            return "medium"
        return "low"

    return "medium"


def _extract_number(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1))


def _extract_duration_minutes(text: str, *, label_pattern: str) -> float | None:
    labeled = re.search(
        rf"{label_pattern}[^0-9]{{0,12}}(?:(\d{{1,2}})\s*(?:小时|h))?[^0-9]{{0,4}}(?:(\d{{1,3}})\s*(?:分钟|min))?",
        text,
        flags=re.IGNORECASE,
    )
    if labeled and (labeled.group(1) or labeled.group(2)):
        hours = int(labeled.group(1) or 0)
        minutes = int(labeled.group(2) or 0)
        return float(hours * 60 + minutes)

    plain_minutes = re.search(rf"{label_pattern}[^0-9]{{0,8}}(\d{{1,3}})", text, flags=re.IGNORECASE)
    if plain_minutes:
        return float(plain_minutes.group(1))
    return None

"""Tests for badminton coach health screenshot analysis."""

from deerflow.domain.coach.health_image import analyze_health_image_text, build_health_recovery_advice


def test_analyze_heart_rate_screenshot_text():
    observation = analyze_health_image_text(
        "羽毛球 1小时26分钟 最高心率 184 bpm 平均心率 162 bpm 消耗 786 千卡"
    )
    advice = build_health_recovery_advice(observation)

    assert observation.screenshot_type == "heart_rate"
    assert observation.risk_level == "high"
    assert observation.observed_metrics["max_hr"] == 184
    assert any("高强度区间" in item for item in observation.observations)
    assert "恢复或低强度" in advice.next_session_intensity


def test_analyze_sleep_recovery_screenshot_text():
    observation = analyze_health_image_text(
        "昨晚睡眠 5小时18分钟 深睡 41 分钟 HRV 28 静息心率 61"
    )
    advice = build_health_recovery_advice(observation)

    assert observation.screenshot_type == "sleep_recovery"
    assert observation.risk_level == "high"
    assert observation.observed_metrics["hrv"] == 28
    assert any("HRV 偏低" in item for item in observation.observations)
    assert any("恢复为主" in item for item in advice.recovery_actions)


def test_analyze_training_load_screenshot_text():
    observation = analyze_health_image_text(
        "训练负荷 168 恢复时间 32 小时 羽毛球 时长 102 分钟 卡路里 822"
    )
    advice = build_health_recovery_advice(observation)

    assert observation.screenshot_type == "training_load"
    assert observation.risk_level == "high"
    assert observation.observed_metrics["training_load"] == 168
    assert observation.observed_metrics["recovery_hours"] == 32
    assert any("训练负荷偏高" in item for item in observation.observations)
    assert "高强度" in advice.recovery_actions[1]

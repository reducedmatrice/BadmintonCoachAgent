"""Tests for badminton coach postmatch extraction rules."""

from deerflow.domain.coach.postmatch import extract_postmatch_review


def test_extract_postmatch_observations_and_next_focus():
    review = extract_postmatch_review(
        "今天后场步法还是慢，回位总跟不上。反手更敢发力了。下次重点继续盯后场启动和反手稳定性。"
    )

    assert any(item.topic == "后场步法" for item in review.technical_observations)
    assert any("跟不上" in item.evidence for item in review.technical_observations)
    assert any(item.topic == "反手稳定性" for item in review.improvements)
    assert "后场步法" in review.next_focus
    assert "反手稳定性" in review.next_focus


def test_postmatch_does_not_turn_pure_emotion_into_technical_fact():
    review = extract_postmatch_review("今天有点着急，心态一般，但其实也没什么特别明显的技术问题。")

    assert review.technical_observations == []
    assert review.emotional_notes == ["今天有点着急，心态一般，但其实也没什么特别明显的技术问题"]


def test_postmatch_handles_mixed_review_without_losing_improvement():
    review = extract_postmatch_review(
        "今天杀球衔接还是不够顺，不过封网比上次更稳了，接下来优先练杀球后第一步回位。"
    )

    assert any(item.topic == "杀球衔接" for item in review.technical_observations)
    assert any(item.topic == "封网衔接" for item in review.improvements)
    assert "杀球衔接" in review.next_focus

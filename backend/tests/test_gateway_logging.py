import logging

from app.gateway.app import LarkNoiseFilter


def _record(message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="Lark",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_lark_noise_filter_suppresses_ignored_processor_events() -> None:
    filter_ = LarkNoiseFilter()

    assert not filter_.filter(
        _record(
            "handle message failed, err: processor not found, "
            "type: im.message.message_read_v1"
        )
    )
    assert not filter_.filter(
        _record(
            "handle message failed, err: processor not found, "
            "type: im.message.reaction.created_v1"
        )
    )


def test_lark_noise_filter_keeps_actionable_errors() -> None:
    filter_ = LarkNoiseFilter()

    assert filter_.filter(_record("connect failed, err: SSLEOFError"))
    assert filter_.filter(
        _record("handle message failed, err: processor not found, type: im.message.receive_v1")
    )

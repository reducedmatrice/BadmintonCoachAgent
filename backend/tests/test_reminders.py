"""Tests for proactive reminder scheduling."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.channels.message_bus import MessageBus
from app.channels.reminders import ReminderScheduler, ReminderStateStore


class MemoryReminderStateStore(ReminderStateStore):
    def __init__(self):
        self._data = {}

    def has_sent(self, slot_key: str) -> bool:
        return slot_key in self._data

    def mark_sent(self, slot_key: str, timestamp: str) -> None:
        self._data[slot_key] = timestamp


@pytest.mark.anyio
async def test_dispatch_due_reminders_respects_time_and_idempotency():
    bus = MessageBus()
    received = []

    async def capture(msg):
        received.append(msg)

    bus.publish_inbound = capture
    scheduler = ReminderScheduler(
        bus,
        channels_config={
            "feishu": {
                "enabled": True,
                "reminders": {
                    "enabled": True,
                    "jobs": [
                        {
                            "name": "weekday-training",
                            "chat_id": "chat-1",
                            "user_id": "coach-reminder",
                            "weekdays": ["MON"],
                            "time": "18:00",
                            "prompt": "提醒我今晚训练前注意热身。",
                        }
                    ],
                },
            }
        },
        state_store=MemoryReminderStateStore(),
    )

    monday_due = datetime.fromisoformat("2026-03-23T18:00:00+08:00")
    monday_late = datetime.fromisoformat("2026-03-23T18:00:30+08:00")
    tuesday_same_time = datetime.fromisoformat("2026-03-24T18:00:00+08:00")

    assert await scheduler.dispatch_due_reminders(monday_due) == 1
    assert await scheduler.dispatch_due_reminders(monday_late) == 0
    assert await scheduler.dispatch_due_reminders(tuesday_same_time) == 0

    assert len(received) == 1
    assert received[0].channel_name == "feishu"
    assert received[0].topic_id == "reminder:weekday-training"
    assert received[0].metadata["scheduled_reminder"] is True


@pytest.mark.anyio
async def test_channel_service_reports_reminder_status():
    from app.channels.service import ChannelService

    service = ChannelService(
        channels_config={
            "feishu": {
                "enabled": False,
                "reminders": {
                    "enabled": True,
                    "jobs": [
                        {
                            "name": "weekday-training",
                            "chat_id": "chat-1",
                            "time": "18:00",
                        }
                    ],
                },
            }
        }
    )

    await service.start()
    status = service.get_status()
    await service.stop()

    assert status["reminders"]["job_count"] == 1

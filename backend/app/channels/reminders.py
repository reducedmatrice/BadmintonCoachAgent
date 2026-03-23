"""Lightweight proactive reminder scheduler for IM channels."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.channels.message_bus import InboundMessage
from deerflow.config.paths import get_paths

logger = logging.getLogger(__name__)

_WEEKDAY_INDEX = {
    "MON": 0,
    "TUE": 1,
    "WED": 2,
    "THU": 3,
    "FRI": 4,
    "SAT": 5,
    "SUN": 6,
}

_DEFAULT_REMINDER_PROMPT = "请基于我的历史档案、最近训练记录和今天天气，生成一条训练前主动提醒，包含重点、风险和一句明确行动建议。"


@dataclass
class ReminderJob:
    channel_name: str
    name: str
    chat_id: str
    user_id: str
    time: str
    weekdays: list[str]
    prompt: str
    topic_id: str


class ReminderStateStore:
    """Persist dispatched reminder slots for idempotency."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            path = get_paths().base_dir / "channels" / "reminder_state.json"
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupt reminder state store at %s, resetting", self._path)
            return {}

    def has_sent(self, slot_key: str) -> bool:
        return slot_key in self._data

    def mark_sent(self, slot_key: str, timestamp: str) -> None:
        self._data[slot_key] = timestamp
        self._path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ReminderScheduler:
    """Periodically publish due proactive reminder requests into the message bus."""

    def __init__(
        self,
        bus,
        *,
        channels_config: dict[str, Any],
        state_store: ReminderStateStore | None = None,
        poll_interval_seconds: int = 30,
    ) -> None:
        self.bus = bus
        self._jobs = _load_reminder_jobs(channels_config)
        self._state_store = state_store or ReminderStateStore()
        self._poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def jobs(self) -> list[ReminderJob]:
        return list(self._jobs)

    async def start(self) -> None:
        if self._running or not self._jobs:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def dispatch_due_reminders(self, now: datetime | None = None) -> int:
        current = now or datetime.now().astimezone()
        count = 0
        for job in self._jobs:
            if not _is_due(job, current):
                continue
            slot_key = _slot_key(job, current)
            if self._state_store.has_sent(slot_key):
                continue
            inbound = InboundMessage(
                channel_name=job.channel_name,
                chat_id=job.chat_id,
                user_id=job.user_id,
                text=job.prompt,
                topic_id=job.topic_id,
                metadata={
                    "scheduled_reminder": True,
                    "reminder_name": job.name,
                    "scheduled_for": current.replace(second=0, microsecond=0).isoformat(),
                },
            )
            await self.bus.publish_inbound(inbound)
            self._state_store.mark_sent(slot_key, current.isoformat())
            count += 1
        return count

    async def _run_loop(self) -> None:
        while self._running:
            try:
                dispatched = await self.dispatch_due_reminders()
                if dispatched:
                    logger.info("ReminderScheduler dispatched %d reminder(s)", dispatched)
            except Exception:
                logger.exception("ReminderScheduler dispatch failed")
            await asyncio.sleep(self._poll_interval_seconds)


def _load_reminder_jobs(channels_config: dict[str, Any]) -> list[ReminderJob]:
    jobs: list[ReminderJob] = []
    for channel_name, config in channels_config.items():
        if not isinstance(config, dict):
            continue
        reminder_config = config.get("reminders")
        if not isinstance(reminder_config, dict) or not reminder_config.get("enabled", False):
            continue
        raw_jobs = reminder_config.get("jobs", [])
        if not isinstance(raw_jobs, list):
            continue
        for raw_job in raw_jobs:
            if not isinstance(raw_job, dict):
                continue
            name = str(raw_job.get("name", "")).strip()
            chat_id = str(raw_job.get("chat_id", "")).strip()
            time_value = str(raw_job.get("time", "")).strip()
            if not name or not chat_id or not time_value:
                continue
            weekdays = [str(item).upper() for item in raw_job.get("weekdays", []) if str(item).upper() in _WEEKDAY_INDEX]
            jobs.append(
                ReminderJob(
                    channel_name=channel_name,
                    name=name,
                    chat_id=chat_id,
                    user_id=str(raw_job.get("user_id", "coach-reminder")).strip() or "coach-reminder",
                    time=time_value,
                    weekdays=weekdays,
                    prompt=str(raw_job.get("prompt", _DEFAULT_REMINDER_PROMPT)).strip() or _DEFAULT_REMINDER_PROMPT,
                    topic_id=str(raw_job.get("topic_id", f"reminder:{name}")).strip() or f"reminder:{name}",
                )
            )
    return jobs


def _is_due(job: ReminderJob, now: datetime) -> bool:
    try:
        hour_str, minute_str = job.time.split(":", 1)
        hour = int(hour_str)
        minute = int(minute_str)
    except (ValueError, TypeError):
        return False

    if job.weekdays and now.weekday() not in {_WEEKDAY_INDEX[item] for item in job.weekdays}:
        return False
    return now.hour == hour and now.minute == minute


def _slot_key(job: ReminderJob, now: datetime) -> str:
    return f"{job.channel_name}:{job.name}:{now.strftime('%Y-%m-%dT%H:%M')}"

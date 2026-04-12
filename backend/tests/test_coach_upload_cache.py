from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from deerflow.config.paths import Paths
from deerflow.domain.coach.upload_cache import cleanup_multimodal_upload_cache, write_multimodal_upload_manifest


def _make_paths(base_dir: Path) -> Paths:
    return Paths(base_dir=base_dir)


def test_cleanup_multimodal_upload_cache_deletes_verified_old_files(tmp_path: Path):
    paths = _make_paths(tmp_path)
    thread_id = "thread-a"
    paths.ensure_thread_dirs(thread_id)
    upload = paths.sandbox_uploads_dir(thread_id) / "run.png"
    upload.write_bytes(b"img")

    review_log = paths.agent_dir("badminton-coach") / "memory" / "reviews" / "2026-04-01.md"
    review_log.parent.mkdir(parents=True, exist_ok=True)
    review_log.write_text("ok", encoding="utf-8")
    profile_path = paths.agent_dir("badminton-coach") / "coach_profile.json"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text("{}", encoding="utf-8")

    with patch("deerflow.domain.coach.upload_cache.get_paths", return_value=paths):
        write_multimodal_upload_manifest(
            upload,
            status="success",
            thread_id=thread_id,
            wrote_event_evidence=True,
            updated_profile=True,
            review_log_path=str(review_log),
            profile_path=str(profile_path),
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
        )
        result = cleanup_multimodal_upload_cache(
            retention_days=30,
            now=datetime(2026, 4, 12, tzinfo=UTC),
        )

    assert result["deleted"] == 1
    assert upload.exists() is False


def test_cleanup_multimodal_upload_cache_skips_missing_writeback_artifacts(tmp_path: Path):
    paths = _make_paths(tmp_path)
    thread_id = "thread-b"
    paths.ensure_thread_dirs(thread_id)
    upload = paths.sandbox_uploads_dir(thread_id) / "run2.png"
    upload.write_bytes(b"img")

    missing_review_log = paths.agent_dir("badminton-coach") / "memory" / "reviews" / "missing.md"
    with patch("deerflow.domain.coach.upload_cache.get_paths", return_value=paths):
        write_multimodal_upload_manifest(
            upload,
            status="success",
            thread_id=thread_id,
            wrote_event_evidence=True,
            updated_profile=False,
            review_log_path=str(missing_review_log),
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
        result = cleanup_multimodal_upload_cache(
            retention_days=30,
            now=datetime(2026, 4, 12, tzinfo=UTC),
        )

    assert result["deleted"] == 0
    assert result["skipped"] >= 1
    assert upload.exists() is True


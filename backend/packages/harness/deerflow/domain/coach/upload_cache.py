"""Governance helpers for multimodal upload cache."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from deerflow.config.paths import get_paths

_MANIFEST_SUFFIX = ".coach-mm.json"


def _iso_now(now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    return current.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        return None


def _manifest_path(upload_path: Path) -> Path:
    return upload_path.with_name(f"{upload_path.name}{_MANIFEST_SUFFIX}")


def write_multimodal_upload_manifest(
    upload_path: Path,
    *,
    status: str,
    thread_id: str,
    wrote_event_evidence: bool,
    updated_profile: bool,
    review_log_path: str | None = None,
    profile_path: str | None = None,
    reason: str | None = None,
    error_type: str | None = None,
    created_at: datetime | None = None,
) -> Path:
    """Write sidecar manifest for one multimodal upload."""
    manifest = {
        "version": 1,
        "status": status,
        "thread_id": thread_id,
        "upload_path": str(upload_path),
        "wrote_event_evidence": wrote_event_evidence,
        "updated_profile": updated_profile,
        "review_log_path": review_log_path or "",
        "profile_path": profile_path or "",
        "reason": reason or "",
        "error_type": error_type or "",
        "created_at": _iso_now(created_at),
    }
    target = _manifest_path(upload_path)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def cleanup_multimodal_upload_cache(
    *,
    retention_days: int = 30,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Cleanup cached multimodal uploads with writeback verification.

    Delete only when all conditions hold:
    - sidecar status is success
    - sidecar age >= retention_days
    - required writeback artifacts exist:
      - wrote_event_evidence => review_log_path exists
      - updated_profile => profile_path exists
    """
    paths = get_paths()
    base_threads = paths.base_dir / "threads"
    if not base_threads.exists():
        return {"scanned": 0, "deleted": 0, "skipped": 0, "errors": []}

    threshold = (now or datetime.now(UTC)).astimezone(UTC) - timedelta(days=max(retention_days, 0))
    scanned = 0
    deleted = 0
    skipped = 0
    errors: list[str] = []

    for manifest_path in base_threads.glob(f"*/user-data/uploads/*{_MANIFEST_SUFFIX}"):
        scanned += 1
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            status = str(payload.get("status") or "")
            if status != "success":
                skipped += 1
                continue

            created_at = _parse_iso(payload.get("created_at"))
            if created_at is None:
                skipped += 1
                errors.append(f"invalid_created_at:{manifest_path}")
                continue
            if created_at > threshold:
                skipped += 1
                continue

            wrote_event = bool(payload.get("wrote_event_evidence"))
            updated_profile = bool(payload.get("updated_profile"))
            review_log_path = str(payload.get("review_log_path") or "")
            profile_path = str(payload.get("profile_path") or "")

            if wrote_event and (not review_log_path or not Path(review_log_path).exists()):
                skipped += 1
                errors.append(f"missing_review_log:{manifest_path}")
                continue
            if updated_profile and (not profile_path or not Path(profile_path).exists()):
                skipped += 1
                errors.append(f"missing_profile:{manifest_path}")
                continue

            upload_path = Path(str(payload.get("upload_path") or ""))
            if upload_path.exists():
                upload_path.unlink()
            manifest_path.unlink(missing_ok=True)
            deleted += 1
        except Exception as exc:
            skipped += 1
            errors.append(f"cleanup_error:{manifest_path}:{type(exc).__name__}")

    return {"scanned": scanned, "deleted": deleted, "skipped": skipped, "errors": errors}


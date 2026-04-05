"""Deterministic dedupe keys for structured log imports."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class StructuredLogDedupeKeys:
    dedupe_hash: str
    source_line_hash: str


def canonicalize_structured_log_payload(payload: Mapping[str, Any]) -> str:
    """Serialize a structured log payload into a stable JSON string."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_dedupe_hash(payload: Mapping[str, Any]) -> str:
    """Hash the canonical structured log payload."""
    canonical_payload = canonicalize_structured_log_payload(payload)
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def compute_source_line_hash(source_file: str | Path, line_number: int, dedupe_hash: str) -> str:
    """Hash the source location and payload identity for idempotent inserts."""
    if line_number < 1:
        raise ValueError("line_number must be >= 1")

    normalized_source = Path(source_file).as_posix()
    raw = f"{normalized_source}:{line_number}:{dedupe_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_structured_log_dedupe_keys(
    payload: Mapping[str, Any],
    *,
    source_file: str | Path,
    line_number: int,
) -> StructuredLogDedupeKeys:
    """Build both payload-level and source-line-level dedupe keys."""
    dedupe_hash = compute_dedupe_hash(payload)
    source_line_hash = compute_source_line_hash(source_file, line_number, dedupe_hash)
    return StructuredLogDedupeKeys(dedupe_hash=dedupe_hash, source_line_hash=source_line_hash)

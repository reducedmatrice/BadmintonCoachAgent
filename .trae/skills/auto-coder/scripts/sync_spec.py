#!/usr/bin/env python3
"""
Spec Sync — splits the selected dev spec into chapter files under auto-coder/references/.

Usage:
    python scripts/sync_spec.py [selector] [--force]
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import List, Tuple, NamedTuple


class Chapter(NamedTuple):
    number: int
    cn_title: str
    filename: str
    start_line: int
    end_line: int
    line_count: int


# Chapter number -> English slug (encoding-independent)
NUMBER_SLUG_MAP = {
    1: "overview",
    2: "features",
    3: "tech-stack",
    4: "testing",
    5: "architecture",
    6: "schedule",
    7: "future",
}


def _slug(chapter_num: int, title: str) -> str:
    if chapter_num in NUMBER_SLUG_MAP:
        return NUMBER_SLUG_MAP[chapter_num]
    # Fallback: sanitize whatever title text we have
    clean = re.sub(r'[^\w]+', '-', title, flags=re.ASCII).strip('-').lower()
    return clean or f"chapter-{chapter_num}"


def detect_chapters(content: str) -> List[Chapter]:
    lines = content.split('\n')
    starts: List[Tuple[int, str, int]] = []
    for i, line in enumerate(lines):
        m = re.match(r'^## (\d+)\.\s+(.+)$', line)
        if m:
            starts.append((int(m.group(1)), m.group(2).strip(), i))
    if not starts:
        raise ValueError("No chapters found. Expected '## N. Title'")
    chapters = []
    for idx, (num, title, start) in enumerate(starts):
        end = starts[idx + 1][2] if idx + 1 < len(starts) else len(lines)
        chapters.append(Chapter(num, title, f"{num:02d}-{_slug(num, title)}.md", start, end, end - start))
    return chapters


def _normalize_selector(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def resolve_active_spec(repo_root: Path, selector: str | None = None) -> Path:
    all_specs = sorted(path for path in repo_root.glob("dev-spec*.md"))

    if selector:
        raw_selector = selector.strip()
        selector_no_ext = raw_selector.removesuffix(".md")
        explicit_candidates = [
            repo_root / raw_selector,
            repo_root / f"{selector_no_ext}.md",
        ]
        for candidate in explicit_candidates:
            if candidate.exists():
                return candidate

        normalized_selector = _normalize_selector(selector_no_ext)
        matches: list[tuple[int, int, str, Path]] = []
        for path in all_specs:
            stem = path.stem
            normalized_stem = _normalize_selector(stem)
            version_match = re.search(r"(\d+(?:\.\d+)*)", stem)
            version = version_match.group(1) if version_match else ""
            normalized_version = _normalize_selector(version)

            score = -1
            if normalized_stem == normalized_selector:
                score = 300
            elif normalized_version and normalized_version == normalized_selector:
                score = 250
            elif normalized_selector in normalized_stem:
                score = 200
            elif normalized_version and normalized_version in normalized_selector:
                score = 150

            if score >= 0:
                matches.append((score, -len(stem), path.name, path))

        if matches:
            matches.sort(reverse=True)
            return matches[0][3]

        raise FileNotFoundError(f"No spec matched selector: {selector}")

    preferred = repo_root / "dev-spec.md"
    if preferred.exists():
        return preferred

    versioned = sorted(
        (
            path for path in all_specs
            if path.name != "dev-spec1.0.md"
        ),
        key=lambda path: path.name,
    )
    if versioned:
        return versioned[-1]

    raise FileNotFoundError("No active spec found. Expected dev-spec.md or a versioned dev-spec*.md file.")


def sync(force: bool = False, selector: str | None = None):
    skill_dir = Path(__file__).parent.parent          # auto-coder/
    repo_root = skill_dir.parent.parent.parent        # project root
    dev_spec = resolve_active_spec(repo_root, selector=selector)
    specs_dir = skill_dir / "references"
    hash_file = skill_dir / ".spec_hash"

    if not dev_spec.exists():
        print(f"ERROR: active spec not found: {dev_spec.name}")
        sys.exit(1)

    # Hash check
    current_hash = hashlib.sha256(dev_spec.read_bytes()).hexdigest()
    if not force and hash_file.exists() and hash_file.read_text().strip() == current_hash:
        print("specs up-to-date"); return

    content = dev_spec.read_text(encoding='utf-8')
    chapters = detect_chapters(content)
    lines = content.split('\n')

    specs_dir.mkdir(parents=True, exist_ok=True)

    # Clean orphans
    old = {f.name for f in specs_dir.glob("*.md")}
    new = {ch.filename for ch in chapters}
    for f in old - new:
        (specs_dir / f).unlink()

    # Write chapters
    for ch in chapters:
        (specs_dir / ch.filename).write_text('\n'.join(lines[ch.start_line:ch.end_line]), encoding='utf-8')

    hash_file.write_text(current_hash)
    print(f"synced {len(chapters)} chapters from {dev_spec.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("selector", nargs="?", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    sync(force=args.force, selector=args.selector)

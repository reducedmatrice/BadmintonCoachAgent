"""Memory updater for reading, writing, and updating memory data."""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from deerflow.agents.memory.prompt import (
    MEMORY_UPDATE_PROMPT,
    format_conversation_for_update,
)
from deerflow.agents.memory.schema import (
    build_memory_entry_path,
    build_trace_metadata,
    empty_context_section,
    generate_memory_entry_id,
    isoformat_z,
    normalize_sources,
    normalize_thread_ids,
    render_memory_entry_markdown,
)
from deerflow.config.memory_config import get_memory_config
from deerflow.config.paths import get_paths
from deerflow.models import create_chat_model


def _get_memory_file_path(agent_name: str | None = None) -> Path:
    """Get the path to the memory file.

    Args:
        agent_name: If provided, returns the per-agent memory file path.
                    If None, returns the global memory file path.

    Returns:
        Path to the memory file.
    """
    if agent_name is not None:
        return get_paths().agent_memory_file(agent_name)

    config = get_memory_config()
    if config.storage_path:
        p = Path(config.storage_path)
        # Absolute path: use as-is; relative path: resolve against base_dir
        return p if p.is_absolute() else get_paths().base_dir / p
    return get_paths().memory_file


def _create_empty_memory() -> dict[str, Any]:
    """Create an empty memory structure."""
    return {
        "version": "1.0",
        "lastUpdated": isoformat_z(),
        "user": {
            "workContext": empty_context_section(),
            "personalContext": empty_context_section(),
            "topOfMind": empty_context_section(),
        },
        "history": {
            "recentMonths": empty_context_section(),
            "earlierContext": empty_context_section(),
            "longTermBackground": empty_context_section(),
        },
        "facts": [],
    }


def _get_memory_owner_root(agent_name: str | None = None) -> Path:
    """Return the directory that owns the memory index and markdown entries."""
    if agent_name is not None:
        return get_paths().agent_dir(agent_name)
    return get_paths().base_dir


# Per-agent memory cache: keyed by agent_name (None = global)
# Value: (memory_data, file_mtime)
_memory_cache: dict[str | None, tuple[dict[str, Any], float | None]] = {}


def get_memory_data(agent_name: str | None = None) -> dict[str, Any]:
    """Get the current memory data (cached with file modification time check).

    The cache is automatically invalidated if the memory file has been modified
    since the last load, ensuring fresh data is always returned.

    Args:
        agent_name: If provided, loads per-agent memory. If None, loads global memory.

    Returns:
        The memory data dictionary.
    """
    file_path = _get_memory_file_path(agent_name)

    # Get current file modification time
    try:
        current_mtime = file_path.stat().st_mtime if file_path.exists() else None
    except OSError:
        current_mtime = None

    cached = _memory_cache.get(agent_name)

    # Invalidate cache if file has been modified or doesn't exist
    if cached is None or cached[1] != current_mtime:
        memory_data = _load_memory_from_file(agent_name)
        _memory_cache[agent_name] = (memory_data, current_mtime)
        return memory_data

    return cached[0]


def reload_memory_data(agent_name: str | None = None) -> dict[str, Any]:
    """Reload memory data from file, forcing cache invalidation.

    Args:
        agent_name: If provided, reloads per-agent memory. If None, reloads global memory.

    Returns:
        The reloaded memory data dictionary.
    """
    file_path = _get_memory_file_path(agent_name)
    memory_data = _load_memory_from_file(agent_name)

    try:
        mtime = file_path.stat().st_mtime if file_path.exists() else None
    except OSError:
        mtime = None

    _memory_cache[agent_name] = (memory_data, mtime)
    return memory_data


def _load_memory_from_file(agent_name: str | None = None) -> dict[str, Any]:
    """Load memory data from file.

    Args:
        agent_name: If provided, loads per-agent memory file. If None, loads global.

    Returns:
        The memory data dictionary.
    """
    file_path = _get_memory_file_path(agent_name)

    if not file_path.exists():
        return _create_empty_memory()

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        return _normalize_memory_shape(data)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Failed to load memory file: {e}")
        return _create_empty_memory()


def _normalize_memory_shape(memory_data: dict[str, Any]) -> dict[str, Any]:
    """Backfill new traceability fields for legacy memory payloads."""
    normalized = _create_empty_memory()
    normalized.update(
        {
            "version": memory_data.get("version", normalized["version"]),
            "lastUpdated": memory_data.get("lastUpdated", normalized["lastUpdated"]),
        }
    )

    for section_name in ("user", "history"):
        section_payload = memory_data.get(section_name, {})
        if not isinstance(section_payload, dict):
            continue

        for key, default_value in normalized[section_name].items():
            raw_value = section_payload.get(key, {})
            if not isinstance(raw_value, dict):
                continue
            normalized[section_name][key] = {
                "summary": raw_value.get("summary", ""),
                "updatedAt": raw_value.get("updatedAt", ""),
                "sources": normalize_sources(raw_value.get("sources")),
                "thread_ids": normalize_thread_ids(raw_value.get("thread_ids")),
            }

    normalized_facts: list[dict[str, Any]] = []
    for fact in memory_data.get("facts", []):
        if not isinstance(fact, dict):
            continue
        normalized_facts.append(
            {
                "id": fact.get("id", f"fact_{uuid.uuid4().hex[:8]}"),
                "content": fact.get("content", ""),
                "category": fact.get("category", "context"),
                "confidence": fact.get("confidence", 0.5),
                "createdAt": fact.get("createdAt", ""),
                "source": fact.get("source", "unknown"),
                "sources": normalize_sources(fact.get("sources")),
                "thread_ids": normalize_thread_ids(fact.get("thread_ids"), fact.get("source")),
            }
        )
    normalized["facts"] = normalized_facts
    return normalized


# Matches sentences that describe a file-upload *event* rather than general
# file-related work.  Deliberately narrow to avoid removing legitimate facts
# such as "User works with CSV files" or "prefers PDF export".
_UPLOAD_SENTENCE_RE = re.compile(
    r"[^.!?]*\b(?:"
    r"upload(?:ed|ing)?(?:\s+\w+){0,3}\s+(?:file|files?|document|documents?|attachment|attachments?)"
    r"|file\s+upload"
    r"|/mnt/user-data/uploads/"
    r"|<uploaded_files>"
    r")[^.!?]*[.!?]?\s*",
    re.IGNORECASE,
)


def _strip_upload_mentions_from_memory(memory_data: dict[str, Any]) -> dict[str, Any]:
    """Remove sentences about file uploads from all memory summaries and facts.

    Uploaded files are session-scoped; persisting upload events in long-term
    memory causes the agent to search for non-existent files in future sessions.
    """
    # Scrub summaries in user/history sections
    for section in ("user", "history"):
        section_data = memory_data.get(section, {})
        for _key, val in section_data.items():
            if isinstance(val, dict) and "summary" in val:
                cleaned = _UPLOAD_SENTENCE_RE.sub("", val["summary"]).strip()
                cleaned = re.sub(r"  +", " ", cleaned)
                val["summary"] = cleaned

    # Also remove any facts that describe upload events
    facts = memory_data.get("facts", [])
    if facts:
        memory_data["facts"] = [f for f in facts if not _UPLOAD_SENTENCE_RE.search(f.get("content", ""))]

    return memory_data


def _save_memory_to_file(memory_data: dict[str, Any], agent_name: str | None = None) -> bool:
    """Save memory data to file and update cache.

    Args:
        memory_data: The memory data to save.
        agent_name: If provided, saves to per-agent memory file. If None, saves to global.

    Returns:
        True if successful, False otherwise.
    """
    file_path = _get_memory_file_path(agent_name)

    try:
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Update lastUpdated timestamp
        memory_data["lastUpdated"] = isoformat_z()

        # Write atomically using temp file
        temp_path = file_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(memory_data, f, indent=2, ensure_ascii=False)

        # Rename temp file to actual file (atomic on most systems)
        temp_path.replace(file_path)

        # Update cache and file modification time
        try:
            mtime = file_path.stat().st_mtime
        except OSError:
            mtime = None

        _memory_cache[agent_name] = (memory_data, mtime)

        print(f"Memory saved to {file_path}")
        return True
    except OSError as e:
        print(f"Failed to save memory file: {e}")
        return False


def _summarize_messages_for_entry(messages: list[Any]) -> tuple[str, str]:
    """Build lightweight user/assistant summaries from conversation messages."""
    user_parts: list[str] = []
    assistant_parts: list[str] = []

    for message in messages:
        content = getattr(message, "content", "")
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
            content = "\n".join(text_parts)

        if not isinstance(content, str):
            continue

        text = content.strip()
        if not text:
            continue

        msg_type = getattr(message, "type", "")
        if msg_type == "human":
            user_parts.append(text)
        elif msg_type == "ai":
            assistant_parts.append(text)

    user_summary = "\n\n".join(user_parts[-3:]).strip()
    assistant_summary = "\n\n".join(assistant_parts[-3:]).strip()
    return user_summary, assistant_summary


def _extract_signals_from_update(update_data: dict[str, Any]) -> list[str]:
    """Build simple trace signals for the markdown entry."""
    signals: list[str] = []

    for section_group in ("user", "history"):
        group = update_data.get(section_group, {})
        if not isinstance(group, dict):
            continue
        for name, payload in group.items():
            if isinstance(payload, dict) and payload.get("shouldUpdate") and payload.get("summary"):
                signals.append(f"{section_group}.{name}")

    for fact in update_data.get("newFacts", []):
        if not isinstance(fact, dict):
            continue
        category = fact.get("category", "context")
        content = fact.get("content", "")
        if isinstance(content, str) and content.strip():
            signals.append(f"fact:{category}:{content.strip()[:80]}")

    for fact_id in update_data.get("factsToRemove", []):
        if isinstance(fact_id, str) and fact_id:
            signals.append(f"remove_fact:{fact_id}")

    deduped: list[str] = []
    for signal in signals:
        if signal not in deduped:
            deduped.append(signal)
    return deduped


def _append_memory_entry(
    messages: list[Any],
    thread_id: str,
    agent_name: str | None = None,
) -> dict[str, Any] | None:
    """Append a markdown memory entry and return its trace metadata."""
    owner_root = _get_memory_owner_root(agent_name)
    now = isoformat_z()
    entry_id = generate_memory_entry_id()
    entry_path = build_memory_entry_path(owner_root)
    user_summary, assistant_summary = _summarize_messages_for_entry(messages)
    entry_markdown = render_memory_entry_markdown(
        entry_id=entry_id,
        thread_id=thread_id,
        ts=now,
        user_summary=user_summary,
        assistant_summary=assistant_summary,
    )

    try:
        entry_path.parent.mkdir(parents=True, exist_ok=True)
        if entry_path.exists() and entry_path.stat().st_size > 0:
            prefix = "\n\n"
        else:
            prefix = ""
        with open(entry_path, "a", encoding="utf-8") as f:
            f.write(prefix + entry_markdown)
    except OSError as e:
        print(f"Failed to append memory entry: {e}")
        return None

    return {
        "entry_id": entry_id,
        "entry_path": str(entry_path),
        "timestamp": now,
        "thread_id": thread_id,
    }


def _rewrite_memory_entry_signals(entry_path: Path, entry_id: str, signals: list[str]) -> None:
    """Patch the just-appended entry's signal block with extracted signals."""
    if not signals:
        return

    try:
        content = entry_path.read_text(encoding="utf-8")
        marker = f"## {entry_id}"
        start = content.rfind(marker)
        if start < 0:
            return

        entry_text = content[start:]
        replacement = "### Extracted Signals\n\n" + "\n".join(f"- {signal}" for signal in signals) + "\n"
        updated_entry_text = re.sub(
            r"### Extracted Signals\n\n(?:- .*\n?)+",
            replacement,
            entry_text,
            count=1,
        )
        entry_path.write_text(content[:start] + updated_entry_text, encoding="utf-8")
    except OSError as e:
        print(f"Failed to rewrite memory entry signals: {e}")


class MemoryUpdater:
    """Updates memory using LLM based on conversation context."""

    def __init__(self, model_name: str | None = None):
        """Initialize the memory updater.

        Args:
            model_name: Optional model name to use. If None, uses config or default.
        """
        self._model_name = model_name

    def _get_model(self):
        """Get the model for memory updates."""
        config = get_memory_config()
        model_name = self._model_name or config.model_name
        return create_chat_model(name=model_name, thinking_enabled=False)

    def update_memory(self, messages: list[Any], thread_id: str | None = None, agent_name: str | None = None) -> bool:
        """Update memory based on conversation messages.

        Args:
            messages: List of conversation messages.
            thread_id: Optional thread ID for tracking source.
            agent_name: If provided, updates per-agent memory. If None, updates global memory.

        Returns:
            True if update was successful, False otherwise.
        """
        config = get_memory_config()
        if not config.enabled:
            return False

        if not messages:
            return False

        try:
            # Get current memory
            current_memory = get_memory_data(agent_name)

            # Format conversation for prompt
            conversation_text = format_conversation_for_update(messages)

            if not conversation_text.strip():
                return False

            # Build prompt
            prompt = MEMORY_UPDATE_PROMPT.format(
                current_memory=json.dumps(current_memory, indent=2),
                conversation=conversation_text,
            )

            # Call LLM
            model = self._get_model()
            response = model.invoke(prompt)
            response_text = str(response.content).strip()

            # Parse response
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            update_data = json.loads(response_text)

            # File-first memory: append source entry before writing the index.
            if not thread_id:
                print("Memory update aborted: thread_id is required for file-first memory indexing")
                return False

            entry_metadata = _append_memory_entry(messages, thread_id=thread_id, agent_name=agent_name)
            if entry_metadata is None:
                print("Memory update aborted: markdown entry append failed")
                return False

            # Apply updates
            updated_memory = self._apply_updates(current_memory, update_data, thread_id, entry_metadata)

            if entry_metadata:
                _rewrite_memory_entry_signals(
                    Path(entry_metadata["entry_path"]),
                    entry_metadata["entry_id"],
                    _extract_signals_from_update(update_data),
                )

            # Strip file-upload mentions from all summaries before saving.
            # Uploaded files are session-scoped and won't exist in future sessions,
            # so recording upload events in long-term memory causes the agent to
            # try (and fail) to locate those files in subsequent conversations.
            updated_memory = _strip_upload_mentions_from_memory(updated_memory)

            # Save
            return _save_memory_to_file(updated_memory, agent_name)

        except json.JSONDecodeError as e:
            print(f"Failed to parse LLM response for memory update: {e}")
            return False
        except Exception as e:
            print(f"Memory update failed: {e}")
            return False

    def _apply_updates(
        self,
        current_memory: dict[str, Any],
        update_data: dict[str, Any],
        thread_id: str | None = None,
        entry_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply LLM-generated updates to memory.

        Args:
            current_memory: Current memory data.
            update_data: Updates from LLM.
            thread_id: Optional thread ID for tracking.

        Returns:
            Updated memory data.
        """
        config = get_memory_config()
        now = isoformat_z()
        entry_sources = [entry_metadata["entry_id"]] if entry_metadata and entry_metadata.get("entry_id") else []

        # Update user sections
        user_updates = update_data.get("user", {})
        for section in ["workContext", "personalContext", "topOfMind"]:
            section_data = user_updates.get(section, {})
            if section_data.get("shouldUpdate") and section_data.get("summary"):
                sources, thread_ids = build_trace_metadata(sources=entry_sources, thread_id=thread_id)
                current_memory["user"][section] = {
                    "summary": section_data["summary"],
                    "updatedAt": now,
                    "sources": sources,
                    "thread_ids": thread_ids,
                }

        # Update history sections
        history_updates = update_data.get("history", {})
        for section in ["recentMonths", "earlierContext", "longTermBackground"]:
            section_data = history_updates.get(section, {})
            if section_data.get("shouldUpdate") and section_data.get("summary"):
                sources, thread_ids = build_trace_metadata(sources=entry_sources, thread_id=thread_id)
                current_memory["history"][section] = {
                    "summary": section_data["summary"],
                    "updatedAt": now,
                    "sources": sources,
                    "thread_ids": thread_ids,
                }

        # Remove facts
        facts_to_remove = set(update_data.get("factsToRemove", []))
        if facts_to_remove:
            current_memory["facts"] = [f for f in current_memory.get("facts", []) if f.get("id") not in facts_to_remove]

        # Add new facts
        new_facts = update_data.get("newFacts", [])
        for fact in new_facts:
            confidence = fact.get("confidence", 0.5)
            if confidence >= config.fact_confidence_threshold:
                if not entry_sources:
                    continue
                sources, thread_ids = build_trace_metadata(
                    sources=entry_sources + normalize_sources(fact.get("sources")),
                    thread_id=thread_id,
                    thread_ids=fact.get("thread_ids"),
                )
                fact_entry = {
                    "id": f"fact_{uuid.uuid4().hex[:8]}",
                    "content": fact.get("content", ""),
                    "category": fact.get("category", "context"),
                    "confidence": confidence,
                    "createdAt": now,
                    "source": thread_id or "unknown",
                    "sources": sources,
                    "thread_ids": thread_ids,
                }
                current_memory["facts"].append(fact_entry)

        # Enforce max facts limit
        if len(current_memory["facts"]) > config.max_facts:
            # Sort by confidence and keep top ones
            current_memory["facts"] = sorted(
                current_memory["facts"],
                key=lambda f: f.get("confidence", 0),
                reverse=True,
            )[: config.max_facts]

        return current_memory


def update_memory_from_conversation(messages: list[Any], thread_id: str | None = None, agent_name: str | None = None) -> bool:
    """Convenience function to update memory from a conversation.

    Args:
        messages: List of conversation messages.
        thread_id: Optional thread ID.
        agent_name: If provided, updates per-agent memory. If None, updates global memory.

    Returns:
        True if successful, False otherwise.
    """
    updater = MemoryUpdater()
    return updater.update_memory(messages, thread_id, agent_name)

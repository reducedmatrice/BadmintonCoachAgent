"""Configuration and loaders for custom agents."""

import json
import logging
import re
from typing import Any

import yaml
from pydantic import BaseModel

from deerflow.config.paths import get_paths

logger = logging.getLogger(__name__)

SOUL_FILENAME = "SOUL.md"
PERSONALITIES_DIRNAME = "personalities"
PERSONALITY_META_FILENAME = "meta.json"
PERSONALITY_PERSONA_FILENAME = "persona.md"
AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")
PERSONALITY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class AgentConfig(BaseModel):
    """Configuration for a custom agent."""

    name: str
    description: str = ""
    model: str | None = None
    tool_groups: list[str] | None = None
    default_personality: str | None = None


class AgentPersonalityAsset(BaseModel):
    """Loaded personality asset for a custom agent."""

    id: str
    persona: str
    meta: dict[str, Any] = {}

    @property
    def style(self) -> dict[str, Any] | None:
        raw_style = self.meta.get("style")
        if isinstance(raw_style, dict):
            return dict(raw_style)
        return None


def load_agent_config(name: str | None) -> AgentConfig | None:
    """Load the custom or default agent's config from its directory.

    Args:
        name: The agent name.

    Returns:
        AgentConfig instance.

    Raises:
        FileNotFoundError: If the agent directory or config.yaml does not exist.
        ValueError: If config.yaml cannot be parsed.
    """

    if name is None:
        return None

    if not AGENT_NAME_PATTERN.match(name):
        raise ValueError(f"Invalid agent name '{name}'. Must match pattern: {AGENT_NAME_PATTERN.pattern}")
    agent_dir = get_paths().agent_dir(name)
    config_file = agent_dir / "config.yaml"

    if not agent_dir.exists():
        raise FileNotFoundError(f"Agent directory not found: {agent_dir}")

    if not config_file.exists():
        raise FileNotFoundError(f"Agent config not found: {config_file}")

    try:
        with open(config_file, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse agent config {config_file}: {e}") from e

    # Ensure name is set from directory name if not in file
    if "name" not in data:
        data["name"] = name

    # Strip unknown fields before passing to Pydantic (e.g. legacy prompt_file)
    known_fields = set(AgentConfig.model_fields.keys())
    data = {k: v for k, v in data.items() if k in known_fields}

    return AgentConfig(**data)


def load_agent_soul(agent_name: str | None) -> str | None:
    """Read the SOUL.md file for a custom agent, if it exists.

    SOUL.md defines the agent's personality, values, and behavioral guardrails.
    It is injected into the lead agent's system prompt as additional context.

    Args:
        agent_name: The name of the agent or None for the default agent.

    Returns:
        The SOUL.md content as a string, or None if the file does not exist.
    """
    agent_dir = get_paths().agent_dir(agent_name) if agent_name else get_paths().base_dir
    soul_path = agent_dir / SOUL_FILENAME
    if not soul_path.exists():
        return None
    content = soul_path.read_text(encoding="utf-8").strip()
    return content or None


def _resolve_personality_id(agent_name: str | None, personality_id: str | None = None) -> str | None:
    candidate = (personality_id or "").strip() or None
    if candidate:
        if not PERSONALITY_ID_PATTERN.match(candidate):
            logger.warning("Invalid personality_id '%s'; ignoring.", candidate)
            return None
        return candidate

    if not agent_name:
        return None

    try:
        agent_config = load_agent_config(agent_name)
    except (FileNotFoundError, ValueError):
        return None

    candidate = (agent_config.default_personality or "").strip() or None
    if not candidate:
        return None
    if not PERSONALITY_ID_PATTERN.match(candidate):
        logger.warning("Agent '%s' has invalid default_personality '%s'; ignoring.", agent_name, candidate)
        return None
    return candidate


def load_agent_personality(
    agent_name: str | None,
    personality_id: str | None = None,
) -> AgentPersonalityAsset | None:
    """Load the selected persona asset for a custom agent.

    Personality selection order:
    1. Explicit `personality_id`
    2. Agent config `default_personality`

    Invalid or missing personalities should not break runtime assembly.
    """
    if not agent_name:
        return None

    resolved_id = _resolve_personality_id(agent_name, personality_id)
    if not resolved_id:
        return None

    agent_dir = get_paths().agent_dir(agent_name)
    personality_dir = agent_dir / PERSONALITIES_DIRNAME / resolved_id
    persona_path = personality_dir / PERSONALITY_PERSONA_FILENAME
    if not persona_path.exists():
        logger.warning("Personality persona.md not found for agent '%s': %s", agent_name, persona_path)
        return None

    persona = persona_path.read_text(encoding="utf-8").strip()
    if not persona:
        logger.warning("Personality persona.md is empty for agent '%s': %s", agent_name, persona_path)
        return None

    meta_path = personality_dir / PERSONALITY_META_FILENAME
    meta: dict[str, Any] = {}
    if meta_path.exists():
        try:
            raw_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse personality meta for agent '%s' (%s): %s", agent_name, meta_path, exc)
        else:
            if isinstance(raw_meta, dict):
                meta = raw_meta
            else:
                logger.warning("Ignoring non-object personality meta for agent '%s': %s", agent_name, meta_path)

    return AgentPersonalityAsset(id=resolved_id, persona=persona, meta=meta)


def load_agent_personality_prompt(agent_name: str | None, personality_id: str | None = None) -> str | None:
    """Return selected personality prompt text for prompt injection."""
    asset = load_agent_personality(agent_name, personality_id=personality_id)
    if asset is None:
        return None
    return asset.persona


def load_agent_personality_style(agent_name: str | None, personality_id: str | None = None) -> dict[str, Any] | None:
    """Return selected personality style config for programmatic renderers."""
    asset = load_agent_personality(agent_name, personality_id=personality_id)
    if asset is None:
        return None
    return asset.style


def list_custom_agents() -> list[AgentConfig]:
    """Scan the agents directory and return all valid custom agents.

    Returns:
        List of AgentConfig for each valid agent directory found.
    """
    agents_dir = get_paths().agents_dir

    if not agents_dir.exists():
        return []

    agents: list[AgentConfig] = []

    for entry in sorted(agents_dir.iterdir()):
        if not entry.is_dir():
            continue

        config_file = entry / "config.yaml"
        if not config_file.exists():
            logger.debug(f"Skipping {entry.name}: no config.yaml")
            continue

        try:
            agent_cfg = load_agent_config(entry.name)
            agents.append(agent_cfg)
        except Exception as e:
            logger.warning(f"Skipping agent '{entry.name}': {e}")

    return agents

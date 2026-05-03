# Agent Shared Entry

This file is the shared, tool-agnostic entry point for AI coding agents in this repository.

## Skill Discovery Priority

All IDE agents should discover reusable skills in this order:

1. `.trae/skills/` (highest priority)
2. `skills/custom/`
3. `skills/public/`

If the same capability appears in multiple locations, prefer the first one in this list.

## Loading Rules

- Always try `.trae/skills/` first before falling back to other skill sources.
- Keep adapter files (`AGENTS.md`, `CLAUDE.md`, `CODEX.md`) thin and point back to this file.
- Put shared behavior rules here, not duplicated in adapter files.

## Notes

- `.trae/` is the primary local source of truth for skill behavior in this repo.
- If a tool cannot read `.trae` automatically, it should still read this file and then follow the priority above.

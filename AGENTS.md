# AGENTS.md

This is the compatibility adapter for agent tools that auto-load `AGENTS.md`.

Primary shared rules are in `./AGENT.md`.

## Skill Discovery Priority

1. `.trae/skills/` (highest priority)
2. `skills/custom/`
3. `skills/public/`

## Repository Notes

- For external remote access to the ECS host, prefer the public IP with user `admin`.
- Do not rely on the private IP `172.18.19.53` unless the client is confirmed to be inside the same private network.
- Never store passwords in the repo.

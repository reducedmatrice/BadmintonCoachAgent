---
name: docker-deploy
description: Use this skill when deploying note-agent / DeerFlow to the remote Docker server, reviewing a deployment, fixing server Docker runtime issues, or preparing the next production update. It covers the required paths, env files, data mounts, Docker compose commands, Feishu channel pitfalls, and post-deploy checks.
---

# DeerFlow Docker Deploy

## Purpose

Use this skill to deploy this repo to the server Docker stack and to debug deployment-only failures that do not reproduce locally.

The target deployment is `docker/docker-compose.yaml` with compose project `deer-flow`, external port `2026`, code under `/home/ubuntu/projects/note-agent`, and runtime data under `/home/ubuntu/data/deer-flow`.

## Critical Differences From Local

- `localhost` inside a container means that container itself. Use `http://langgraph:2024` for gateway-to-langgraph traffic.
- Docker mounts `${DEER_FLOW_HOME}` to `/app/backend/.deer-flow`; this hides the repo's `backend/.deer-flow` inside the container.
- Root `.env` is loaded by backend services via `env_file: ../.env`; `frontend/.env` is loaded by the frontend service.
- Feishu WebSocket should run once. Keep gateway at `--workers 1` unless a leader election mechanism exists.
- Do not delete `/home/ubuntu/data/deer-flow`; it contains runtime state, checkpoints, channel store, secrets, and agent data.

## Required Server Files

In `/home/ubuntu/projects/note-agent`:

```bash
.env
config.yaml
extensions_config.json
frontend/.env
```

In `/home/ubuntu/data/deer-flow`:

```bash
agents/badminton-coach/
.better-auth-secret
```

If `agents/badminton-coach` is missing on a new server, seed it from the repo:

```bash
mkdir -p /home/ubuntu/data/deer-flow/agents
cp -a /home/ubuntu/projects/note-agent/backend/.deer-flow/agents/badminton-coach /home/ubuntu/data/deer-flow/agents/
```

## Deployment Environment

Before running compose or `scripts/deploy.sh`, export:

```bash
export DEER_FLOW_HOME=/home/ubuntu/data/deer-flow
export DEER_FLOW_CONFIG_PATH=/home/ubuntu/projects/note-agent/config.yaml
export DEER_FLOW_EXTENSIONS_CONFIG_PATH=/home/ubuntu/projects/note-agent/extensions_config.json
export DEER_FLOW_REPO_ROOT=/home/ubuntu/projects/note-agent
export DEER_FLOW_DOCKER_SOCKET=/var/run/docker.sock
export PORT=2026
export BETTER_AUTH_SECRET="$(cat /home/ubuntu/data/deer-flow/.better-auth-secret)"
```

## Normal Update Workflow

1. Check out the intended commit:

```bash
cd /home/ubuntu/projects/note-agent
git fetch --all --tags
git checkout <target_sha>
```

2. Verify required files and runtime seed data:

```bash
test -f .env
test -f frontend/.env
test -f config.yaml
test -f extensions_config.json
test -d /home/ubuntu/data/deer-flow/agents/badminton-coach
```

3. Verify Docker-only config values:

```bash
grep -n "langgraph_url:" config.yaml
grep -n -- "--workers 1" docker/docker-compose.yaml
```

Expected:

```yaml
channels:
  langgraph_url: http://langgraph:2024
```

4. Deploy through the repo entrypoint:

```bash
sudo -E ./scripts/deploy.sh
```

If changing only compose command or mounted source files and avoiding rebuild is appropriate, use:

```bash
docker compose -p deer-flow -f docker/docker-compose.yaml up -d --no-build --force-recreate gateway
```

## Post-Deploy Checks

```bash
docker compose -p deer-flow -f docker/docker-compose.yaml ps
curl -I http://127.0.0.1:2026
curl -I http://127.0.0.1:2026/api/langgraph/docs
docker logs --tail=120 deer-flow-gateway
docker logs --tail=120 deer-flow-langgraph
```

Healthy Feishu text flow should show:

```text
Feishu channel started
parsed message
runs.stream
streaming response completed
running card updated
```

There should be one gateway container and one Feishu WebSocket connection.

## Common Failure Signatures

- `httpx.ConnectError: All connection attempts failed`: gateway is probably using `localhost:2024`; use `http://langgraph:2024`.
- `Agent directory not found: /app/backend/.deer-flow/agents/badminton-coach`: seed `/home/ubuntu/data/deer-flow/agents/badminton-coach`.
- Duplicate Feishu replies or repeated events: check duplicate gateway containers and ensure gateway uses `--workers 1`.
- `processor not found` for `im.message.message_read_v1` or `im.message.reaction.created_v1`: register or keep no-op handlers; these are Feishu event noise, not the main text chain.
- Build stalls on Python dependencies: confirm backend Dockerfile uses mainland PyPI mirrors and fallback index.

## Safety Rules

- Never paste secrets or `.env` values into chat or logs.
- Never remove `/home/ubuntu/data/deer-flow` during routine deploys.
- Prefer Git commit deployment over local tarball deployment.
- Preserve server `.env`, `frontend/.env`, `config.yaml`, and `extensions_config.json` unless explicitly replacing them.

# Backend Development Dockerfile
ARG PYTHON_BASE_IMAGE=docker.m.daocloud.io/library/python:3.12-slim
FROM ${PYTHON_BASE_IMAGE}

ARG NODE_MAJOR=22
ARG PYPI_PRIMARY_INDEX=https://mirrors.aliyun.com/pypi/simple/
ARG PYPI_FALLBACK_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple

# Use a mainland mirror for Debian packages to reduce build latency on CN servers.
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g; s|http://deb.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g; s|http://deb.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list; \
    fi

# Install system dependencies + Node.js (provides npx for MCP servers)
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    gnupg \
    ca-certificates \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install uv with mainland mirrors first and a secondary fallback to reduce
# build stalls on servers with unstable external connectivity.
RUN set -eux; \
    python -m pip install --no-cache-dir --disable-pip-version-check --retries 8 --timeout 120 -i "${PYPI_PRIMARY_INDEX}" uv \
    || python -m pip install --no-cache-dir --disable-pip-version-check --retries 8 --timeout 120 -i "${PYPI_FALLBACK_INDEX}" uv

# Set working directory
WORKDIR /app

# Copy frontend source code
COPY backend ./backend

# Install dependencies with cache mount and a mainland package index.
RUN --mount=type=cache,target=/root/.cache/uv \
    sh -c "cd backend && uv sync --default-index ${PYPI_PRIMARY_INDEX} --index ${PYPI_FALLBACK_INDEX}"

# Expose ports (gateway: 8001, langgraph: 2024)
EXPOSE 8001 2024

# Default command (can be overridden in docker-compose)
CMD ["sh", "-c", "cd backend && PYTHONPATH=. uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001"]

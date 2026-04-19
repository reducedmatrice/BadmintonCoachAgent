#!/usr/bin/env python3
"""Minimal probe for the current OpenAI-compatible gateway configuration."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required env: {name}")
    return value


def main() -> int:
    base_url = _require_env("DEERFLOW_OPENAI_BASE_URL").rstrip("/")
    api_key = _require_env("DEERFLOW_OPENAI_API_KEY")
    model = _require_env("DEERFLOW_OPENAI_MODEL")

    endpoint = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 8,
        "temperature": 0,
        "stream": False,
    }

    parsed = urllib.parse.urlparse(base_url)
    print(f"base_url_host={parsed.netloc}")
    print(f"base_url_path={parsed.path or '/'}")
    print(f"model={model}")
    print("api_key_present=True")

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"http_status={exc.code}")
        print(body[:800])
        return 1
    except urllib.error.URLError as exc:
        print(f"network_error={exc.reason}")
        return 2

    print("http_status=200")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print(body[:800])
        return 3

    choices = data.get("choices") or []
    if not choices:
        print(json.dumps(data, ensure_ascii=False)[:800])
        return 4

    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        content = "".join(text_parts)

    print(f"reply={str(content).strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

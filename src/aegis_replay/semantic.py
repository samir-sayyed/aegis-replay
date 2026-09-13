"""Fail-safe semantic selection around a provider-neutral transport."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Selection:
    ids: tuple[str, ...]
    fallback: bool
    reason: str
    cache_key: str


def litellm_transport(
    base_url: str,
    model: str,
    api_key: str,
    request: Callable[[str, dict[str, str], dict, int], dict] | None = None,
) -> Callable[[dict], str]:
    """Return a bounded, zero-temperature LiteLLM-compatible transport."""
    if not base_url.startswith("https://") or not model or not api_key:
        raise ValueError("LiteLLM endpoint, model, and API key are required")
    post = _post_json if request is None else request

    def transport(prompt: dict) -> str:
        body = {
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Return only JSON with selected array and uncertain boolean."},
                {"role": "user", "content": json.dumps(prompt, sort_keys=True, separators=(",", ":"))},
            ],
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        error: Exception | None = None
        for _ in range(2):
            try:
                response = post(base_url.rstrip("/") + "/chat/completions", headers, body, 10)
                content = response["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise ValueError("LiteLLM response content is malformed")
                return content
            except Exception as current:
                error = current
        raise RuntimeError("LiteLLM request failed") from error

    return transport


def _post_json(endpoint: str, headers: dict[str, str], body: dict, timeout: int) -> dict:
    request = Request(endpoint, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - endpoint requires HTTPS above
        decoded = json.loads(response.read().decode())
    if not isinstance(decoded, dict):
        raise ValueError("LiteLLM response is malformed")
    return decoded


def select(candidates: list[str], deterministic: set[str], prompt: dict, transport: Callable[[dict], str], cache_directory: Path | None = None) -> Selection:
    key = hashlib.sha256(json.dumps(prompt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    cache = cache_directory / f"{key}.json" if cache_directory else None
    if cache and cache.is_file():
        response = cache.read_text()
    else:
        try:
            response = transport({**prompt, "temperature": 0, "candidates": candidates})
        except Exception:
            return Selection(tuple(sorted(candidates)), True, "provider failure", key)
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(response)
    try:
        decoded = json.loads(response)
        selected = decoded["selected"]
        uncertain = decoded.get("uncertain", False)
        if not isinstance(selected, list) or not isinstance(uncertain, bool) or any(not isinstance(value, str) or value not in candidates for value in selected):
            raise ValueError
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return Selection(tuple(sorted(candidates)), True, "invalid response", key)
    if uncertain:
        return Selection(tuple(sorted(set(candidates) | deterministic)), True, "model uncertainty", key)
    return Selection(tuple(sorted(set(selected) | deterministic)), False, "additive semantic selection", key)

"""Fail-safe semantic selection around a provider-neutral transport."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Selection:
    ids: tuple[str, ...]
    fallback: bool
    reason: str
    cache_key: str


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

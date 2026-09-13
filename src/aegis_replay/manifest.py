"""Sanitized immutable selection-manifest storage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


FORBIDDEN = ("token", "password", "authorization", "diff", "description", "summary")


def write(repository: Path, inputs: dict[str, str], rankings: list[dict], selected: list[str], fallback: str, model: str, prompt_version: str) -> Path:
    if any(any(word in key.lower() for word in FORBIDDEN) for key in inputs):
        raise ValueError("manifest inputs contain sensitive or raw content")
    body = {"schema_version": 1, "input_hashes": dict(sorted(inputs.items())), "rankings": rankings, "selected": sorted(selected), "fallback": fallback, "model": model, "prompt_version": prompt_version}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    destination = repository / ".aegis" / "manifests" / f"{digest}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return destination

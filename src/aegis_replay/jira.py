"""Sanitized Jira Cloud intent snapshots from recorded API payloads."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


class JiraError(ValueError):
    pass


KEY = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
SENSITIVE = re.compile(r"(?:gh[pousr]_[A-Za-z0-9]+|sk-[A-Za-z0-9]+|bearer\s+\S+|(?:password|token)\s*=\s*\S+)", re.I)


def detect_key(*texts: str, override: str | None = None) -> str:
    if override:
        if not KEY.fullmatch(override):
            raise JiraError("Jira key is malformed")
        return override
    found = [match.group(1) for text in texts for match in KEY.finditer(text or "")]
    if not found:
        raise JiraError("no Jira key found")
    return found[0]


def capture(repository: Path, payload: dict, key: str) -> Path:
    fields = payload.get("fields") if isinstance(payload, dict) else None
    if not isinstance(fields, dict) or payload.get("key") != key:
        raise JiraError("Jira payload does not match requested ticket")
    snapshot = {"schema_version": 1, "key": key, "summary": _text(fields.get("summary")), "description": _text(fields.get("description")), "acceptance_criteria": _text(fields.get("acceptance_criteria")), "issue_type": _name(fields.get("issuetype")), "labels": _strings(fields.get("labels")), "components": _names(fields.get("components")), "parent": _name(fields.get("parent"))}
    snapshot["content_sha256"] = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    destination = repository / ".aegis" / "jira" / f"{key}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    return destination


def _text(value: object) -> str:
    value = value if isinstance(value, str) else ""
    return SENSITIVE.sub("[redacted]", value)


def _strings(value: object) -> list[str]:
    return [_text(item) for item in value] if isinstance(value, list) and all(isinstance(item, str) for item in value) else []


def _name(value: object) -> str:
    return _text(value.get("name", "")) if isinstance(value, dict) else ""


def _names(value: object) -> list[str]:
    return [_name(item) for item in value] if isinstance(value, list) else []

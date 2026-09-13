"""Sanitized Jira Cloud intent snapshots from recorded API payloads."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


class JiraError(ValueError):
    pass


KEY = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
ANTIBODY_ID = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
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


def capture(repository: Path, payload: dict, key: str, antibody_id: str | None = None) -> Path:
    fields = payload.get("fields") if isinstance(payload, dict) else None
    if not isinstance(fields, dict) or payload.get("key") != key:
        raise JiraError("Jira payload does not match requested ticket")
    snapshot = {"schema_version": 1, "key": key, "summary": _text(fields.get("summary")), "description": _text(fields.get("description")), "acceptance_criteria": _text(fields.get("acceptance_criteria")), "issue_type": _name(fields.get("issuetype")), "labels": _strings(fields.get("labels")), "components": _names(fields.get("components")), "parent": _name(fields.get("parent"))}
    snapshot["content_sha256"] = _snapshot_hash(snapshot)
    destination = repository / ".aegis" / "jira" / f"{key}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    if antibody_id is not None:
        if not ANTIBODY_ID.fullmatch(antibody_id):
            raise JiraError("antibody id is malformed")
        link = repository / ".aegis" / "jira-links" / f"{antibody_id}.json"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.write_text(json.dumps({"schema_version": 1, "key": key, "content_sha256": snapshot["content_sha256"]}, indent=2, sort_keys=True) + "\n")
    return destination


def linked_content_hash(repository: Path, antibody_id: str) -> str | None:
    if not ANTIBODY_ID.fullmatch(antibody_id):
        raise JiraError("antibody id is malformed")
    link_path = repository / ".aegis" / "jira-links" / f"{antibody_id}.json"
    if not link_path.is_file():
        return None
    try:
        link = json.loads(link_path.read_text(encoding="utf-8"))
        key = link["key"]
        digest = link["content_sha256"]
    except (OSError, KeyError, json.JSONDecodeError, TypeError) as error:
        raise JiraError("linked Jira snapshot is malformed") from error
    if not isinstance(key, str) or not KEY.fullmatch(key) or not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise JiraError("linked Jira snapshot is malformed")
    try:
        snapshot = json.loads((repository / ".aegis" / "jira" / f"{key}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise JiraError("linked Jira snapshot is malformed") from error
    if snapshot.get("content_sha256") != digest or _snapshot_hash(snapshot) != digest:
        raise JiraError("linked Jira snapshot content changed")
    return digest


def _text(value: object) -> str:
    value = value if isinstance(value, str) else ""
    return SENSITIVE.sub("[redacted]", value)


def _strings(value: object) -> list[str]:
    return [_text(item) for item in value] if isinstance(value, list) and all(isinstance(item, str) for item in value) else []


def _name(value: object) -> str:
    return _text(value.get("name", "")) if isinstance(value, dict) else ""


def _names(value: object) -> list[str]:
    return [_name(item) for item in value] if isinstance(value, list) else []


def _snapshot_hash(snapshot: dict) -> str:
    content = {key: value for key, value in snapshot.items() if key != "content_sha256"}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()

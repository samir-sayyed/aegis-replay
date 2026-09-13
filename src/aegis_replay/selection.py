"""Repository-backed deterministic candidate selection."""

from __future__ import annotations

import json
from pathlib import Path

from .antibodies import AntibodyError, load
from .jira import JiraError, linked_content_hash
from .ranking import Ranked, rank


class SelectionError(ValueError):
    """Candidate registry cannot be read safely."""


def rank_repository(repository: Path, changed_paths: list[str]) -> list[Ranked]:
    if not changed_paths or not all(_safe_path(path) for path in changed_paths):
        raise SelectionError("changed paths must be safe repository paths")
    records: list[dict[str, object]] = []
    deterministic: set[str] = set()
    for path in sorted((repository / ".aegis" / "antibodies").glob("*.json")):
        try:
            antibody = load(repository, path.stem)
            intent = _intent(repository, antibody.id)
        except (AntibodyError, JiraError, OSError, json.JSONDecodeError) as error:
            raise SelectionError(f"cannot load antibody candidate: {path.stem}") from error
        records.append({"id": antibody.id, "invariant": antibody.invariant, "jira": intent, "scope": antibody.scope})
        if _matches(antibody.scope, changed_paths):
            deterministic.add(antibody.id)
    query = " ".join(changed_paths + [str(record["jira"]) for record in records])
    return rank(query, records, deterministic)


def _intent(repository: Path, antibody_id: str) -> str:
    digest = linked_content_hash(repository, antibody_id)
    if digest is None:
        return ""
    link = json.loads((repository / ".aegis" / "jira-links" / f"{antibody_id}.json").read_text(encoding="utf-8"))
    snapshot = json.loads((repository / ".aegis" / "jira" / f"{link['key']}.json").read_text(encoding="utf-8"))
    return " ".join(str(snapshot.get(field, "")) for field in ("summary", "description", "acceptance_criteria", "labels", "components"))


def _matches(scope: list[str], changed: list[str]) -> bool:
    return any(item == path or item.startswith(path.rstrip("/") + "/") or path.startswith(item.rstrip("/") + "/") for item in scope for path in changed)


def _safe_path(value: object) -> bool:
    return isinstance(value, str) and value and not value.startswith("/") and ".." not in Path(value).parts

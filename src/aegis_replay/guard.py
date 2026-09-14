"""Deterministic fail-closed PR guard selection."""

from __future__ import annotations

import json
from pathlib import Path

from .antibodies import AntibodyError, load
from .approval import ApprovalError, _git_head
from .doctor import DoctorError, diagnose_identities
from .proof import freshness
from .config import load_target
from .batching import plan


def guard(repository: Path, changed_paths: list[str]) -> str:
    candidates = sorted((repository / ".aegis" / "antibodies").glob("*.json"))
    selected = []
    for path in candidates:
        identifier = path.stem
        try:
            antibody = load(repository, identifier)
            if "*" not in changed_paths and not _matches(antibody.scope, changed_paths):
                continue
            if freshness(repository, identifier) != "fresh" or not _approved(repository, identifier):
                return "invalid"
            selected.append(antibody)
        except (AntibodyError, OSError, json.JSONDecodeError):
            return "invalid"
    if not selected:
        return "pass"
    revision = _git_head(repository)
    batches = plan(
        [
            {"id": antibody.id, "target": antibody.target, "revision": revision, "test": (test["class"], test["name"])}
            for antibody in selected
            for test in antibody.tests
        ]
    )
    for items in batches.values():
        try:
            diagnose_identities(load_target(repository / "aegis.yaml", items[0]["target"]), repository, [item["test"] for item in items])
        except DoctorError:
            if not _run_isolated(repository, items):
                return "recurrence"
    return "pass"


def _run_isolated(repository: Path, items: list[dict]) -> bool:
    target = load_target(repository / "aegis.yaml", items[0]["target"])
    try:
        for item in items:
            diagnose_identities(target, repository, [item["test"]])
    except DoctorError:
        return False
    return True


def _matches(scope: list[str], changed: list[str]) -> bool:
    return any(item == path or item.startswith(path.rstrip("/") + "/") or path.startswith(item.rstrip("/") + "/") for item in scope for path in changed)


def _approved(repository: Path, identifier: str) -> bool:
    path = repository / ".aegis" / "approvals" / f"{identifier}.json"
    try:
        approval = json.loads(path.read_text())
        proof = repository / ".aegis" / "proofs" / f"{identifier}.json"
        import hashlib
        return approval["head_sha"] == _git_head(repository) and approval["proof_sha256"] == hashlib.sha256(proof.read_bytes()).hexdigest()
    except (OSError, KeyError, json.JSONDecodeError, ApprovalError):
        return False

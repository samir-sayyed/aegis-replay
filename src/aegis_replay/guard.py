"""Deterministic fail-closed PR guard selection."""

from __future__ import annotations

import json
from pathlib import Path

from .antibodies import AntibodyError, load
from .approval import ApprovalError, _git_head
from .doctor import DoctorError, diagnose_identities, junit_identities
from .proof import freshness
from .config import ConfigurationError, load_target
from .batching import attribute, plan


def guard(repository: Path, changed_paths: list[str], symbols: list[str] | None = None) -> str:
    symbols = symbols or []
    if not changed_paths or any(not _safe_changed_path(path) or path.startswith(".aegis/") for path in changed_paths):
        return "invalid"
    select_all = "*" in changed_paths or any(_global_input(path) for path in changed_paths)
    candidates = sorted((repository / ".aegis" / "antibodies").glob("*.json"))
    selected = []
    for path in candidates:
        identifier = path.stem
        try:
            antibody = load(repository, identifier)
            target = load_target(repository / "aegis.yaml", antibody.target)
            if not select_all and not _matches(antibody.scope + list(target.scope), changed_paths) and not _symbol_matches(antibody.tests, symbols):
                continue
            if freshness(repository, identifier) != "fresh" or not _approved(repository, identifier):
                return "invalid"
            selected.append(antibody)
        except (AntibodyError, ConfigurationError, OSError, json.JSONDecodeError):
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
            result = diagnose_identities(load_target(repository / "aegis.yaml", items[0]["target"]), repository, [item["test"] for item in items])
            requested = {item["test"] for item in items}
            attribute(items, [identity for identity in junit_identities(result) if identity in requested])
        except (ConfigurationError, DoctorError):
            if not _run_isolated(repository, items):
                return "recurrence"
        except ValueError:
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


def _symbol_matches(tests: list[dict[str, str]], symbols: list[str]) -> bool:
    return any(symbol in {test["class"], test["name"], f"{test['class']}#{test['name']}"} for symbol in symbols for test in tests)


def _global_input(path: str) -> bool:
    name = Path(path).name
    return name in {
        "aegis.yaml", "requirements.txt", "uv.lock", "poetry.lock", "Pipfile.lock", "package.json", "package-lock.json",
        "pnpm-lock.yaml", "yarn.lock", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
        "gradle.properties", "Podfile.lock", "Package.swift", "Gemfile.lock",
    } or path.endswith((".xml", ".xcresult"))


def _safe_changed_path(path: object) -> bool:
    return isinstance(path, str) and bool(path) and not path.startswith("/") and ".." not in Path(path).parts


def _approved(repository: Path, identifier: str) -> bool:
    path = repository / ".aegis" / "approvals" / f"{identifier}.json"
    try:
        approval = json.loads(path.read_text())
        proof = repository / ".aegis" / "proofs" / f"{identifier}.json"
        import hashlib
        return approval["proof_sha256"] == hashlib.sha256(proof.read_bytes()).hexdigest()
    except (OSError, KeyError, json.JSONDecodeError, ApprovalError):
        return False

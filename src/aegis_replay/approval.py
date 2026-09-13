"""Canonical GitHub review verification from recorded API fixtures."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


class ApprovalError(RuntimeError):
    pass


def approve(repository: Path, antibody_id: str, fixture_path: Path, required_owners: list[str]) -> Path:
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        head = fixture["pull_request"]["head"]["sha"]
        reviews = fixture["reviews"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ApprovalError("GitHub fixture is malformed") from error
    current = _git_head(repository)
    proof_path = repository / ".aegis" / "proofs" / f"{antibody_id}.json"
    try:
        proof = json.loads(proof_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ApprovalError("current proof is missing") from error
    if head != current or proof.get("source_revision") != current:
        raise ApprovalError("reviewed GitHub head does not match current proof")
    approved = []
    for review in reviews:
        user = review.get("user", {}).get("login") if isinstance(review, dict) else None
        if review.get("state") == "APPROVED" and not review.get("dismissed_at") and review.get("commit_id") == head and user:
            approved.append(user)
    allowed = set(required_owners)
    if not approved or any(user in {"reviewer", "reviewer@your-company.com"} for user in approved):
        raise ApprovalError("no valid non-placeholder GitHub approval")
    if allowed and not any(user in allowed for user in approved):
        raise ApprovalError("approval is not from required owner")
    digest = hashlib.sha256(proof_path.read_bytes()).hexdigest()
    destination = repository / ".aegis" / "approvals" / f"{antibody_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({"schema_version": 1, "antibody_id": antibody_id, "head_sha": head, "proof_sha256": digest, "reviewers": sorted(approved)}, indent=2) + "\n")
    return destination


def _git_head(repository: Path) -> str:
    result = subprocess.run(["git", "-C", str(repository), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    if result.returncode:
        raise ApprovalError("repository has no Git HEAD")
    return result.stdout.strip()

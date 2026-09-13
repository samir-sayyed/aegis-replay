"""Canonical GitHub review verification from recorded API fixtures."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


class ApprovalError(RuntimeError):
    pass


GITHUB_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def approve(
    repository: Path,
    antibody_id: str,
    fixture_path: Path | None,
    required_owners: list[str],
    github_repository: str | None = None,
    pull_number: int | None = None,
) -> Path:
    try:
        fixture = _review_source(fixture_path, github_repository, pull_number)
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


def github_review(repository: str, pull_number: int, request: object | None = None) -> dict[str, object]:
    if not GITHUB_REPOSITORY.fullmatch(repository) or not isinstance(pull_number, int) or pull_number < 1:
        raise ApprovalError("GitHub repository or pull request is malformed")
    fetch = _github_json if request is None else request
    try:
        pull_request = fetch(f"repos/{repository}/pulls/{pull_number}")
        reviews = fetch(f"repos/{repository}/pulls/{pull_number}/reviews?per_page=100")
    except (ApprovalError, KeyError, TypeError) as error:
        raise ApprovalError("GitHub PR review could not be retrieved") from error
    if not isinstance(pull_request, dict) or not isinstance(reviews, list):
        raise ApprovalError("GitHub PR review response is malformed")
    return {"pull_request": pull_request, "reviews": reviews}


def _review_source(fixture_path: Path | None, github_repository: str | None, pull_number: int | None) -> object:
    if fixture_path is not None:
        return json.loads(fixture_path.read_text(encoding="utf-8"))
    if github_repository is not None and pull_number is not None:
        return github_review(github_repository, pull_number)
    raise ApprovalError("GitHub fixture or repository and pull request are required")


def _github_json(endpoint: str) -> object:
    result = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True, check=False)
    if result.returncode:
        raise ApprovalError("GitHub CLI could not retrieve canonical review data")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ApprovalError("GitHub CLI returned malformed review data") from error


def _git_head(repository: Path) -> str:
    result = subprocess.run(["git", "-C", str(repository), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    if result.returncode:
        raise ApprovalError("repository has no Git HEAD")
    return result.stdout.strip()

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from aegis_replay.approval import github_review


def cli(directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "aegis_replay", *arguments], capture_output=True, text=True, check=False)


def git(directory: Path, *arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=directory, capture_output=True, text=True, check=True).stdout.strip()


def fixture_project(directory: Path, state: str = "APPROVED", dismissed: bool = False) -> Path:
    (directory / "source.txt").write_text("base\n")
    git(directory, "init")
    git(directory, "add", ".")
    git(directory, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "base")
    head = git(directory, "rev-parse", "HEAD")
    proof = directory / ".aegis" / "proofs" / "demo.json"
    proof.parent.mkdir(parents=True)
    proof.write_text(json.dumps({"source_revision": head}))
    fixture = directory / "review.json"
    fixture.write_text(json.dumps({"pull_request": {"head": {"sha": head}}, "reviews": [{"user": {"login": "alice"}, "state": state, "dismissed_at": "2026-01-01" if dismissed else None, "commit_id": head}]}))
    return fixture


def test_approval_accepts_exact_current_owner_review(tmp_path: Path) -> None:
    fixture = fixture_project(tmp_path)
    result = cli(tmp_path, "approve", "demo", "--directory", str(tmp_path), "--github-fixture", str(fixture), "--required-owner", "alice")
    assert result.returncode == 0, result.stdout
    approval = json.loads((tmp_path / ".aegis" / "approvals" / "demo.json").read_text())
    assert approval["reviewers"] == ["alice"]


def test_approval_rejects_stale_or_dismissed_review(tmp_path: Path) -> None:
    fixture = fixture_project(tmp_path)
    (tmp_path / "next.txt").write_text("next\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "next")
    stale = cli(tmp_path, "approve", "demo", "--directory", str(tmp_path), "--github-fixture", str(fixture), "--required-owner", "alice")
    assert stale.returncode == 1
    assert "head does not match" in stale.stdout
    dismissed_directory = tmp_path / "dismissed"
    dismissed_directory.mkdir()
    dismissed_fixture = fixture_project(dismissed_directory, dismissed=True)
    dismissed = cli(dismissed_directory, "approve", "demo", "--directory", str(dismissed_directory), "--github-fixture", str(dismissed_fixture), "--required-owner", "alice")
    assert dismissed.returncode == 1
    assert "no valid" in dismissed.stdout


def test_github_review_reads_canonical_pull_head_and_reviews() -> None:
    replies = {
        "repos/acme/replay/pulls/42": {"head": {"sha": "a" * 40}},
        "repos/acme/replay/pulls/42/reviews?per_page=100": [{"user": {"login": "alice"}, "state": "APPROVED", "commit_id": "a" * 40}],
    }
    review = github_review("acme/replay", 42, request=replies.__getitem__)
    assert review["pull_request"]["head"]["sha"] == "a" * 40
    assert review["reviews"][0]["user"]["login"] == "alice"

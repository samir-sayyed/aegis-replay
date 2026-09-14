from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from aegis_replay.antibodies import load
from aegis_replay.config import load_target
from aegis_replay.proof import _current_inputs, _scope_hash
from aegis_replay.guard import _symbol_matches


def cli(directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "aegis_replay", *arguments], capture_output=True, text=True, check=False)


def git(directory: Path, *arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=directory, capture_output=True, text=True, check=True).stdout.strip()


def setup_guard(directory: Path) -> None:
    (directory / "run.py").write_text("from pathlib import Path\nPath('result.xml').write_text('<testsuite><testcase classname=\"x\" name=\"y\"/><testcase classname=\"x\" name=\"control\"/></testsuite>')\n")
    (directory / "aegis.yaml").write_text("schema_version: 1\ntargets:\n  - name: unit\n    runner: command-junit\n    command: ['" + sys.executable + "', 'run.py']\n    junit_xml: result.xml\n")
    git(directory, "init")
    git(directory, "add", ".")
    git(directory, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "base")
    created = cli(directory, "antibody", "create", "guard-demo", "--directory", str(directory), "--invariant", "Guard stays covered", "--target", "unit", "--test", "x#y", "--scope", "src/guard.py", "--proof-input", "source_revision=" + "a" * 64)
    assert created.returncode == 0
    git(directory, "add", ".aegis")
    git(directory, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "antibody")
    head = git(directory, "rev-parse", "HEAD")
    inputs = directory / ".aegis" / "proof-inputs" / "guard-demo"
    inputs.mkdir(parents=True)
    (inputs / "known-bad.patch").write_text("known")
    (inputs / "alternate-bad.patch").write_text("alternate")
    proof = directory / ".aegis" / "proofs" / "guard-demo.json"
    proof.parent.mkdir(exist_ok=True)
    antibody = load(directory, "guard-demo")
    target = load_target(directory / "aegis.yaml", antibody.target)
    proof.write_text(json.dumps({"source_revision": _scope_hash(directory, antibody.scope), "inputs": _current_inputs(directory, antibody, target)}))
    digest = hashlib.sha256(proof.read_bytes()).hexdigest()
    approval = directory / ".aegis" / "approvals" / "guard-demo.json"
    approval.parent.mkdir(exist_ok=True)
    approval.write_text(json.dumps({"head_sha": head, "proof_sha256": digest}))


def test_guard_runs_affected_approved_antibody_and_ignores_unrelated_paths(tmp_path: Path) -> None:
    setup_guard(tmp_path)
    direct = cli(tmp_path, "guard", "--directory", str(tmp_path), "--changed", "src/guard.py")
    assert direct.returncode == 0
    assert "pass" in direct.stdout
    unrelated = cli(tmp_path, "guard", "--directory", str(tmp_path), "--changed", "docs/readme.md")
    assert unrelated.returncode == 0
    assert "pass" in unrelated.stdout


def test_guard_fails_closed_for_stale_matching_proof(tmp_path: Path) -> None:
    setup_guard(tmp_path)
    (tmp_path / "aegis.yaml").write_text((tmp_path / "aegis.yaml").read_text() + "# stale\n")
    result = cli(tmp_path, "guard", "--directory", str(tmp_path), "--changed", "src/guard.py")
    assert result.returncode == 1
    assert "invalid" in result.stdout


def test_guard_fails_closed_when_registry_record_is_deleted_or_dependency_changes(tmp_path: Path) -> None:
    setup_guard(tmp_path)
    deleted = cli(tmp_path, "guard", "--directory", str(tmp_path), "--changed", ".aegis/antibodies/guard-demo.json")
    assert deleted.returncode == 1 and "invalid" in deleted.stdout
    dependency = cli(tmp_path, "guard", "--directory", str(tmp_path), "--changed", "uv.lock")
    assert dependency.returncode == 0 and "pass" in dependency.stdout


def test_guard_fails_closed_for_unsafe_changed_path(tmp_path: Path) -> None:
    setup_guard(tmp_path)
    result = cli(tmp_path, "guard", "--directory", str(tmp_path), "--changed", "../outside.py")
    assert result.returncode == 1 and "invalid" in result.stdout


def test_guard_matches_exact_protected_test_symbols_only() -> None:
    tests = [{"class": "service.Audio", "name": "restores"}]
    assert _symbol_matches(tests, ["service.Audio#restores"])
    assert _symbol_matches(tests, ["restores"])
    assert not _symbol_matches(tests, ["unrelated"])

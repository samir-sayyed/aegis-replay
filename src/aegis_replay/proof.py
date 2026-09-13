"""Three-state, clean-worktree proof execution."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .antibodies import Antibody, AntibodyError, load
from .config import Target, load_target


class ProofError(RuntimeError):
    """A three-state proof cannot be established."""


def prove(repository: Path, antibody: Antibody, known_bad: Path, alternate_bad: Path, control: str) -> Path:
    _require_clean_git(repository)
    control_identity = _identity(control)
    _require_scoped_patch(known_bad, antibody.scope)
    _require_scoped_patch(alternate_bad, antibody.scope)
    target = load_target(repository / "aegis.yaml", antibody.target)
    target_identities = [(test["class"], test["name"]) for test in antibody.tests]
    _run_state(repository, target, "fixed", None, target_identities + [control_identity], True)
    _run_state(repository, target, "known_bad", known_bad, target_identities, False)
    _run_state(repository, target, "alternate_bad", alternate_bad, target_identities, False)
    inputs_directory = repository / ".aegis" / "proof-inputs" / antibody.id
    inputs_directory.mkdir(parents=True, exist_ok=True)
    known_input = inputs_directory / "known-bad.patch"
    alternate_input = inputs_directory / "alternate-bad.patch"
    shutil.copyfile(known_bad, known_input)
    shutil.copyfile(alternate_bad, alternate_input)
    proof = {
        "schema_version": 1,
        "antibody_id": antibody.id,
        "state": "proved",
        "source_revision": _git(repository, "rev-parse", "HEAD").strip(),
        "inputs": {
            "source_sha256": _hash_text(_git(repository, "rev-parse", "HEAD").strip()),
            "configuration_sha256": _hash_file(repository / "aegis.yaml"),
            "tests_sha256": _hash_text(json.dumps(antibody.tests, sort_keys=True)),
            "known_bad_mutation_sha256": _hash_file(known_input),
            "alternate_bad_mutation_sha256": _hash_file(alternate_input),
            "parser_sha256": _hash_file(Path(__file__)),
            "schema_sha256": _hash_text("antibody-v1|proof-v1"),
            "execution_sha256": _hash_text(json.dumps(_execution_input(target), sort_keys=True)),
        },
        "states": {"known_bad": "target-failed", "fixed": "target-and-control-passed", "alternate_bad": "target-failed"},
    }
    destination = repository / ".aegis" / "proofs" / f"{antibody.id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def freshness(repository: Path, antibody_id: str) -> str:
    path = repository / ".aegis" / "proofs" / f"{antibody_id}.json"
    if not path.is_file():
        return "unproved"
    try:
        proof = json.loads(path.read_text(encoding="utf-8"))
        current = _git(repository, "rev-parse", "HEAD").strip()
    except (json.JSONDecodeError, ProofError):
        return "stale"
    if proof.get("source_revision") != current:
        return "stale"
    try:
        antibody = load(repository, antibody_id)
        target = load_target(repository / "aegis.yaml", antibody.target)
        expected = _current_inputs(repository, antibody, target)
    except (AntibodyError, OSError, ProofError):
        return "stale"
    return "fresh" if proof.get("inputs") == expected else "stale"


def _run_state(repository: Path, target: Target, name: str, patch: Path | None, expected: list[tuple[str, str]], passing: bool) -> None:
    with tempfile.TemporaryDirectory(prefix="aegis-proof-") as directory:
        workspace = Path(directory) / name
        _git(repository, "worktree", "add", "--detach", str(workspace), "HEAD")
        try:
            if patch is not None:
                _git(workspace, "apply", "--check", str(patch))
                _git(workspace, "apply", str(patch))
            result = subprocess.run(target.command, cwd=workspace, env={"PATH": os.environ.get("PATH", "")}, capture_output=True, text=True, check=False, timeout=120)
            output = workspace / target.junit_xml
            if not output.is_file():
                raise ProofError(f"{name}: command did not produce JUnit XML")
            actual = _junit_outcomes(output)
            if set(actual) != set(expected) or any(actual[item] != passing for item in expected):
                raise ProofError(f"{name}: JUnit outcomes do not match exact expected tests")
            if passing and result.returncode != 0:
                raise ProofError(f"{name}: passing JUnit run returned {result.returncode}")
            if not passing and result.returncode == 0:
                raise ProofError(f"{name}: failing JUnit run returned success")
        finally:
            _git(repository, "worktree", "remove", "--force", str(workspace))


def _junit_outcomes(path: Path) -> dict[tuple[str, str], bool]:
    try:
        cases = ET.parse(path).getroot().findall(".//testcase")
    except ET.ParseError as error:
        raise ProofError(f"invalid JUnit XML: {error}") from error
    return {(case.attrib.get("classname", ""), case.attrib.get("name", "")): case.find("failure") is None and case.find("error") is None and case.find("skipped") is None for case in cases}


def _identity(value: str) -> tuple[str, str]:
    if value.count("#") != 1:
        raise ProofError("control must use exact class#test-name identity")
    class_name, test_name = value.split("#", 1)
    if not class_name or not test_name:
        raise ProofError("control must use exact class#test-name identity")
    return class_name, test_name


def _require_clean_git(repository: Path) -> None:
    if _git(repository, "status", "--porcelain").strip():
        raise ProofError("proof requires a clean Git workspace")


def _require_scoped_patch(path: Path, scope: list[str]) -> None:
    if not path.is_file():
        raise ProofError(f"mutation is missing: {path}")
    changed = [line[6:] for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("+++ b/")]
    if not changed or any(item not in scope for item in changed):
        raise ProofError("mutation changes files outside antibody scope")


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(["git", "-C", str(repository), *arguments], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ProofError(result.stderr.strip() or "Git operation failed")
    return result.stdout


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _current_inputs(repository: Path, antibody: Antibody, target: Target) -> dict[str, str]:
    inputs_directory = repository / ".aegis" / "proof-inputs" / antibody.id
    return {
        "source_sha256": _hash_text(_git(repository, "rev-parse", "HEAD").strip()),
        "configuration_sha256": _hash_file(repository / "aegis.yaml"),
        "tests_sha256": _hash_text(json.dumps(antibody.tests, sort_keys=True)),
        "known_bad_mutation_sha256": _hash_file(inputs_directory / "known-bad.patch"),
        "alternate_bad_mutation_sha256": _hash_file(inputs_directory / "alternate-bad.patch"),
        "parser_sha256": _hash_file(Path(__file__)),
        "schema_sha256": _hash_text("antibody-v1|proof-v1"),
        "execution_sha256": _hash_text(json.dumps(_execution_input(target), sort_keys=True)),
    }


def _execution_input(target: Target) -> dict[str, object]:
    return {"command": target.command, "directory": target.directory, "environment": target.environment, "junit_xml": target.junit_xml}

"""Strict repository-local antibody records."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import ConfigurationError, _is_safe_relative_path, load_target


class AntibodyError(ValueError):
    """Antibody record is invalid or cannot be stored safely."""


IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
SENSITIVE_VALUE = re.compile(r"(?:gh[pousr]_|sk-|bearer\s+|password\s*=|token\s*=)", re.IGNORECASE)
RECORD_FIELDS = frozenset({"schema_version", "id", "state", "invariant", "target", "tests", "scope", "proof_inputs"})


@dataclass(frozen=True)
class Antibody:
    schema_version: int
    id: str
    state: str
    invariant: str
    target: str
    tests: list[dict[str, str]]
    scope: list[str]
    proof_inputs: dict[str, str]


def create(repository: Path, identifier: str, invariant: str, target: str, test_identities: list[str], scope: list[str], proof_inputs: list[str]) -> Path:
    antibody = Antibody(1, identifier, "draft", invariant, target, _parse_tests(test_identities), _parse_scope(scope), _parse_proof_inputs(proof_inputs))
    _validate(antibody, repository)
    destination = repository / ".aegis" / "antibodies" / f"{identifier}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("x", encoding="utf-8") as output:
            json.dump(asdict(antibody), output, indent=2, sort_keys=True)
            output.write("\n")
    except FileExistsError as error:
        raise AntibodyError(f"antibody already exists: {identifier}") from error
    return destination


def load(repository: Path, identifier: str) -> Antibody:
    if not IDENTIFIER.fullmatch(identifier):
        raise AntibodyError("antibody id is malformed")
    path = repository / ".aegis" / "antibodies" / f"{identifier}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AntibodyError(f"cannot read antibody: {error}") from error
    if not isinstance(raw, dict) or set(raw) != RECORD_FIELDS:
        raise AntibodyError("antibody contains unsupported or missing fields")
    try:
        antibody = Antibody(**raw)
    except TypeError as error:
        raise AntibodyError("antibody has invalid structure") from error
    _validate(antibody, repository)
    return antibody


def explain(antibody: Antibody, freshness: str = "unproved") -> str:
    tests = ", ".join(f"{test['class']}#{test['name']}" for test in antibody.tests)
    return "\n".join((f"Artifact: {antibody.id}", f"State: {antibody.state}", f"Invariant: {antibody.invariant}", f"Target: {antibody.target}", f"Tests: {tests}", f"Scope: {', '.join(antibody.scope)}", f"Freshness: {freshness}"))


def _validate(antibody: Antibody, repository: Path) -> None:
    if antibody.schema_version != 1:
        raise AntibodyError("antibody schema_version must be 1")
    if not isinstance(antibody.id, str) or not IDENTIFIER.fullmatch(antibody.id):
        raise AntibodyError("antibody id is malformed")
    if antibody.state != "draft":
        raise AntibodyError("antibody state is unsupported")
    if not isinstance(antibody.invariant, str) or not antibody.invariant.strip() or SENSITIVE_VALUE.search(antibody.invariant):
        raise AntibodyError("invariant is empty or contains sensitive data")
    try:
        load_target(repository / "aegis.yaml", antibody.target)
    except ConfigurationError as error:
        raise AntibodyError(f"target is not configured: {error}") from error
    if not isinstance(antibody.tests, list) or not antibody.tests:
        raise AntibodyError("antibody requires at least one exact JUnit test")
    if not isinstance(antibody.scope, list) or not antibody.scope:
        raise AntibodyError("antibody requires at least one scope path")
    _parse_tests([f"{item.get('class', '')}#{item.get('name', '')}" if isinstance(item, dict) else "" for item in antibody.tests])
    _parse_scope(antibody.scope)
    _parse_proof_inputs([f"{key}={value}" for key, value in antibody.proof_inputs.items()] if isinstance(antibody.proof_inputs, dict) else [])


def _parse_tests(values: list[str]) -> list[dict[str, str]]:
    if not values:
        raise AntibodyError("antibody requires at least one exact JUnit test")
    parsed = []
    for value in values:
        if not isinstance(value, str) or value.count("#") != 1:
            raise AntibodyError("test must use exact class#test-name identity")
        class_name, test_name = value.split("#", 1)
        if not class_name or not test_name or any(character in value for character in "\n\r") or SENSITIVE_VALUE.search(value):
            raise AntibodyError("test must use exact class#test-name identity")
        parsed.append({"class": class_name, "name": test_name})
    return parsed


def _parse_scope(values: list[str]) -> list[str]:
    if not values or not all(isinstance(value, str) and _is_safe_relative_path(value) for value in values):
        raise AntibodyError("scope must contain only safe relative paths")
    return values


def _parse_proof_inputs(values: list[str]) -> dict[str, str]:
    if not values:
        raise AntibodyError("proof_inputs must contain at least one SHA-256 digest")
    parsed: dict[str, str] = {}
    for value in values:
        if not isinstance(value, str) or value.count("=") != 1:
            raise AntibodyError("proof input must use name=SHA-256")
        name, digest = value.split("=", 1)
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", name) or not SHA256.fullmatch(digest) or name in parsed:
            raise AntibodyError("proof input must use name=SHA-256")
        parsed[name] = digest
    return parsed

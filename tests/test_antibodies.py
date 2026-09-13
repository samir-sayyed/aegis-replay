from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def invoke(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "aegis_replay", *arguments], capture_output=True, text=True, check=False)


def write_config(directory: Path) -> None:
    (directory / "aegis.yaml").write_text(
        "schema_version: 1\ntargets:\n  - name: unit\n    runner: command-junit\n    command: ['python', '-m', 'pytest']\n    junit_xml: reports/junit.xml\n"
    )


def create(directory: Path, identifier: str = "restore-audio") -> subprocess.CompletedProcess[str]:
    return invoke(
        "antibody", "create", identifier, "--directory", str(directory), "--invariant", "Failed restore remains pending", "--target", "unit", "--test", "com.example.RestoreTest#failed restore remains pending", "--scope", "src/restore.py", "--proof-input", "source_revision=" + "a" * 64,
    )


def test_create_stores_strict_repository_local_antibody(tmp_path: Path) -> None:
    write_config(tmp_path)
    result = create(tmp_path)
    assert result.returncode == 0, result.stderr
    record = json.loads((tmp_path / ".aegis" / "antibodies" / "restore-audio.json").read_text())
    assert record["schema_version"] == 1
    assert record["state"] == "draft"
    assert record["target"] == "unit"


def test_explain_reports_record_lifecycle_scope_and_freshness(tmp_path: Path) -> None:
    write_config(tmp_path)
    assert create(tmp_path).returncode == 0
    result = invoke("antibody", "explain", "restore-audio", "--directory", str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "Invariant: Failed restore remains pending" in result.stdout
    assert "State: draft" in result.stdout
    assert "Freshness: unproved" in result.stdout
    assert "Scope: src/restore.py" in result.stdout


def test_create_rejects_duplicate_unsafe_and_malformed_inputs(tmp_path: Path) -> None:
    write_config(tmp_path)
    assert create(tmp_path).returncode == 0
    duplicate = create(tmp_path)
    assert duplicate.returncode == 1
    assert "already exists" in duplicate.stdout
    unsafe_scope = invoke("antibody", "create", "unsafe", "--directory", str(tmp_path), "--invariant", "ok", "--target", "unit", "--test", "com.example.Test#works", "--scope", "../secret.py", "--proof-input", "source_revision=" + "a" * 64)
    assert unsafe_scope.returncode == 1
    assert "safe relative path" in unsafe_scope.stdout
    malformed_test = invoke("antibody", "create", "bad-test", "--directory", str(tmp_path), "--invariant", "ok", "--target", "unit", "--test", "not-a-junit-test", "--scope", "src/test.py", "--proof-input", "source_revision=" + "a" * 64)
    assert malformed_test.returncode == 1
    assert "class#test-name" in malformed_test.stdout


def test_explain_fails_closed_for_unknown_fields_and_unsupported_versions(tmp_path: Path) -> None:
    write_config(tmp_path)
    assert create(tmp_path).returncode == 0
    record_path = tmp_path / ".aegis" / "antibodies" / "restore-audio.json"
    record = json.loads(record_path.read_text())
    record["unknown"] = "not allowed"
    record_path.write_text(json.dumps(record))
    unknown = invoke("antibody", "explain", "restore-audio", "--directory", str(tmp_path))
    assert unknown.returncode == 1
    assert "unsupported or missing fields" in unknown.stdout
    record.pop("unknown")
    record["schema_version"] = 2
    record_path.write_text(json.dumps(record))
    version = invoke("antibody", "explain", "restore-audio", "--directory", str(tmp_path))
    assert version.returncode == 1
    assert "schema_version must be 1" in version.stdout

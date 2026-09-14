from __future__ import annotations

import os
import subprocess
import sys
import json
from pathlib import Path


def invoke(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")}
    return subprocess.run(
        [sys.executable, "-m", "aegis_replay", *arguments], capture_output=True, text=True, check=False, env=environment
    )


def test_init_creates_versioned_generic_target(tmp_path: Path) -> None:
    result = invoke("init", "--directory", str(tmp_path))
    assert result.returncode == 0, result.stderr
    content = (tmp_path / "aegis.yaml").read_text()
    assert "schema_version: 1" in content
    assert "runner: command-junit" in content


def test_jira_capture_detects_branch_key_and_stores_sanitized_snapshot(tmp_path: Path) -> None:
    fixture = tmp_path / "jira.json"
    fixture.write_text(json.dumps({"key": "APP-42", "fields": {"summary": "Restore", "description": "token=secret"}}))
    result = invoke(
        "jira", "capture", "--directory", str(tmp_path), "--branch", "fix/APP-42-restore",
        "--jira-fixture", str(fixture), "--antibody", "sound-restore",
    )
    assert result.returncode == 0, result.stdout
    snapshot = json.loads((tmp_path / ".aegis" / "jira" / "APP-42.json").read_text())
    assert snapshot["description"] == "[redacted]"
    assert (tmp_path / ".aegis" / "jira-links" / "sound-restore.json").is_file()


def test_doctor_executes_one_passing_test_and_verifies_junit(tmp_path: Path) -> None:
    (tmp_path / "make_junit.py").write_text("from pathlib import Path\nPath('result.xml').write_text('<testsuite><testcase classname=\"fixture\" name=\"passes\"/></testsuite>')\n")
    (tmp_path / "aegis.yaml").write_text("schema_version: 1\ntargets:\n  - name: fixture\n    runner: command-junit\n    command: ['" + sys.executable + "', 'make_junit.py']\n    junit_xml: result.xml\n")
    result = invoke("doctor", "--directory", str(tmp_path), "--target", "fixture")
    assert result.returncode == 0, result.stdout
    assert "verified fixture" in result.stdout


def test_doctor_allows_skipped_junit_cases_when_one_case_executed(tmp_path: Path) -> None:
    (tmp_path / "make_junit.py").write_text(
        "from pathlib import Path\n"
        "Path('result.xml').write_text('<testsuite><testcase classname=\"fixture\" name=\"passes\"/><testcase classname=\"fixture\" name=\"not-selected\"><skipped/></testcase></testsuite>')\n"
    )
    (tmp_path / "aegis.yaml").write_text(
        "schema_version: 1\ntargets:\n  - name: fixture\n    runner: command-junit\n"
        "    command: ['" + sys.executable + "', 'make_junit.py']\n    junit_xml: result.xml\n"
    )
    result = invoke("doctor", "--directory", str(tmp_path), "--target", "fixture")
    assert result.returncode == 0, result.stdout


def test_doctor_rejects_shell_syntax(tmp_path: Path) -> None:
    (tmp_path / "aegis.yaml").write_text("schema_version: 1\ntargets:\n  - name: unsafe\n    runner: command-junit\n    command: ['echo; rm']\n    junit_xml: result.xml\n")
    result = invoke("doctor", "--directory", str(tmp_path), "--target", "unsafe")
    assert result.returncode == 1
    assert "shell syntax" in result.stdout


def test_doctor_rejects_unsafe_path_and_disallowed_environment(tmp_path: Path) -> None:
    (tmp_path / "aegis.yaml").write_text("schema_version: 1\ntargets:\n  - name: unsafe\n    runner: command-junit\n    command: ['../tool']\n    junit_xml: ../result.xml\n    environment: {SECRET: nope}\n")
    result = invoke("doctor", "--directory", str(tmp_path), "--target", "unsafe")
    assert result.returncode == 1
    assert "must not traverse" in result.stdout


def test_doctor_rejects_missing_command_and_missing_or_ambiguous_junit(tmp_path: Path) -> None:
    (tmp_path / "aegis.yaml").write_text("schema_version: 1\ntargets:\n  - name: missing-command\n    runner: command-junit\n    command: ['aegis-command-that-does-not-exist']\n    junit_xml: result.xml\n")
    missing_command = invoke("doctor", "--directory", str(tmp_path), "--target", "missing-command")
    assert missing_command.returncode == 1
    assert "command is missing" in missing_command.stdout

    (tmp_path / "make_results.py").write_text("from pathlib import Path\nPath('one.xml').write_text('<testsuite><testcase/></testsuite>')\nPath('two.xml').write_text('<testsuite><testcase/></testsuite>')\n")
    (tmp_path / "aegis.yaml").write_text("schema_version: 1\ntargets:\n  - name: ambiguous\n    runner: command-junit\n    command: ['" + sys.executable + "', 'make_results.py']\n    junit_xml: '*.xml'\n")
    ambiguous = invoke("doctor", "--directory", str(tmp_path), "--target", "ambiguous")
    assert ambiguous.returncode == 1
    assert "exactly one JUnit result" in ambiguous.stdout

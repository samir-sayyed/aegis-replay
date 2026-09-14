"""Safe target diagnosis and JUnit verification."""

from __future__ import annotations

import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from .config import Target


class DoctorError(RuntimeError):
    """Configured target cannot prove one exact passing JUnit result."""


def diagnose(target: Target, repository: Path) -> Path:
    working_directory = repository / target.directory
    executable = target.command[0]
    if "/" in executable:
        command_path = Path(executable) if Path(executable).is_absolute() else working_directory / executable
        if not command_path.is_file() or not os.access(command_path, os.X_OK):
            raise DoctorError(f"command is missing or not executable: {executable}")
    elif shutil.which(executable) is None:
        raise DoctorError(f"command is missing: {executable}")
    _run(target, working_directory)
    result_paths = list(working_directory.glob(target.junit_xml))
    if len(result_paths) != 1:
        raise DoctorError(f"expected exactly one JUnit result, found {len(result_paths)}")
    _verify_junit(result_paths[0])
    return result_paths[0]


def diagnose_identities(target: Target, repository: Path, identities: list[tuple[str, str]]) -> Path:
    """Run one target and verify each requested JUnit identity passed exactly once."""
    working_directory = repository / target.directory
    _run(target, working_directory)
    result_paths = list(working_directory.glob(target.junit_xml))
    if len(result_paths) != 1:
        raise DoctorError(f"expected exactly one JUnit result, found {len(result_paths)}")
    _verify_identities(result_paths[0], identities)
    return result_paths[0]


def junit_identities(result_path: Path) -> list[tuple[str, str]]:
    """Return every executed passing JUnit testcase identity exactly once."""
    try:
        root = ET.parse(result_path).getroot()
    except (OSError, ET.ParseError) as error:
        raise DoctorError(f"invalid JUnit XML: {error}") from error
    identities = []
    for case in root.findall(".//testcase") if root.tag != "testcase" else [root]:
        if case.find("failure") is not None or case.find("error") is not None or case.find("skipped") is not None:
            continue
        identity = (case.attrib.get("classname", ""), case.attrib.get("name", ""))
        if not all(identity) or identity in identities:
            raise DoctorError("JUnit result has an empty or duplicate testcase identity")
        identities.append(identity)
    return identities


def _run(target: Target, repository: Path) -> None:
    environment = {"PATH": os.environ.get("PATH", "")}
    for name in ("JAVA_HOME", "JAVA_HOME_22_ARM64", "JAVA_HOME_22_X64"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    environment.update(target.environment)
    try:
        completed = subprocess.run(target.command, cwd=repository, env=environment, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DoctorError(f"command could not run: {error}") from error
    if completed.returncode != 0:
        raise DoctorError(f"command failed with exit code {completed.returncode}")


def _verify_junit(result_path: Path) -> None:
    try:
        root = ET.parse(result_path).getroot()
    except (OSError, ET.ParseError) as error:
        raise DoctorError(f"invalid JUnit XML: {error}") from error
    tests = root.findall(".//testcase") if root.tag != "testcase" else [root]
    executed = [test for test in tests if test.find("skipped") is None]
    if len(executed) != 1:
        raise DoctorError(f"JUnit result must contain exactly one executed testcase, found {len(executed)}")
    if executed[0].find("failure") is not None or executed[0].find("error") is not None:
        raise DoctorError("JUnit testcase did not pass")


def _verify_identities(result_path: Path, identities: list[tuple[str, str]]) -> None:
    try:
        root = ET.parse(result_path).getroot()
    except (OSError, ET.ParseError) as error:
        raise DoctorError(f"invalid JUnit XML: {error}") from error
    expected = set(identities)
    if len(expected) != len(identities):
        raise DoctorError("expected JUnit identities must be unique")
    found: dict[tuple[str, str], list[ET.Element]] = {}
    for case in root.findall(".//testcase") if root.tag != "testcase" else [root]:
        identity = (case.attrib.get("classname", ""), case.attrib.get("name", ""))
        if identity in expected:
            found.setdefault(identity, []).append(case)
    if set(found) != expected or any(len(cases) != 1 for cases in found.values()):
        raise DoctorError("JUnit result is missing or duplicates an exact antibody testcase")
    if any(case.find("failure") is not None or case.find("error") is not None or case.find("skipped") is not None for cases in found.values() for case in cases):
        raise DoctorError("exact antibody JUnit testcase did not pass")

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


def _run(target: Target, repository: Path) -> None:
    environment = {"PATH": os.environ.get("PATH", ""), **target.environment}
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

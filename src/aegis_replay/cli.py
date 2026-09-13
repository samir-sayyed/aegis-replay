"""Public command-line interface."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .config import ConfigurationError, load_target
from .doctor import DoctorError, diagnose

DEFAULT_CONFIG = {"schema_version": 1, "targets": [{"name": "default", "runner": "command-junit", "command": ["python", "-m", "pytest", "--junitxml=reports/junit.xml"], "junit_xml": "reports/junit.xml"}]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aegis")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="create a starter Aegis configuration")
    init.add_argument("--directory", default=".")
    doctor = commands.add_parser("doctor", help="run and verify one safe JUnit target")
    doctor.add_argument("--directory", default=".")
    doctor.add_argument("--config", default="aegis.yaml")
    doctor.add_argument("--target", default="default")
    args = parser.parse_args(argv)
    if args.command == "init":
        destination = Path(args.directory) / "aegis.yaml"
        if destination.exists():
            parser.error(f"refusing to overwrite existing configuration: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False), encoding="utf-8")
        print(f"Created {destination}")
        return 0
    repository = Path(args.directory).resolve()
    try:
        target = load_target(repository / args.config, args.target)
        result = diagnose(target, repository)
    except (ConfigurationError, DoctorError) as error:
        print(f"Aegis doctor: {error}")
        return 1
    print(f"Aegis doctor: verified {args.target} ({result.relative_to(repository)})")
    return 0

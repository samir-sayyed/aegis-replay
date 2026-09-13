"""Public command-line interface."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .antibodies import AntibodyError, create as create_antibody, explain as explain_antibody, load as load_antibody
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
    antibody = commands.add_parser("antibody", help="create and inspect local antibodies")
    antibody_commands = antibody.add_subparsers(dest="antibody_command", required=True)
    create = antibody_commands.add_parser("create", help="store a strict antibody record")
    create.add_argument("id")
    create.add_argument("--directory", default=".")
    create.add_argument("--invariant", required=True)
    create.add_argument("--target", required=True)
    create.add_argument("--test", action="append", required=True)
    create.add_argument("--scope", action="append", required=True)
    create.add_argument("--proof-input", action="append", required=True)
    explain = antibody_commands.add_parser("explain", help="display an antibody without sensitive data")
    explain.add_argument("id")
    explain.add_argument("--directory", default=".")
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
    if args.command == "antibody":
        try:
            if args.antibody_command == "create":
                record = create_antibody(repository, args.id, args.invariant, args.target, args.test, args.scope, args.proof_input)
                print(f"Created {record.relative_to(repository)}")
            else:
                print(explain_antibody(load_antibody(repository, args.id)))
        except AntibodyError as error:
            print(f"Aegis antibody: {error}")
            return 1
        return 0
    try:
        target = load_target(repository / args.config, args.target)
        result = diagnose(target, repository)
    except (ConfigurationError, DoctorError) as error:
        print(f"Aegis doctor: {error}")
        return 1
    print(f"Aegis doctor: verified {args.target} ({result.relative_to(repository)})")
    return 0

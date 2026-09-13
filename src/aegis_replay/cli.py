"""Public command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .antibodies import AntibodyError, create as create_antibody, explain as explain_antibody, load as load_antibody
from .config import ConfigurationError, load_target
from .doctor import DoctorError, diagnose
from .proof import ProofError, freshness as proof_freshness, prove
from .approval import ApprovalError, approve
from .guard import guard
from .selection import SelectionError, rank_repository

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
    proof = commands.add_parser("prove", help="prove an antibody in three isolated Git states")
    proof.add_argument("id")
    proof.add_argument("--directory", default=".")
    proof.add_argument("--known-bad", required=True)
    proof.add_argument("--alternate-bad", required=True)
    proof.add_argument("--control", required=True)
    approval = commands.add_parser("approve", help="verify canonical GitHub review approval")
    approval.add_argument("id")
    approval.add_argument("--directory", default=".")
    approval_source = approval.add_mutually_exclusive_group(required=True)
    approval_source.add_argument("--github-fixture")
    approval_source.add_argument("--github-repository")
    approval.add_argument("--pull-number", type=int)
    approval.add_argument("--required-owner", action="append", required=True)
    guard_parser = commands.add_parser("guard", help="run deterministic approved PR guards")
    guard_parser.add_argument("--directory", default=".")
    guard_group = guard_parser.add_mutually_exclusive_group(required=True)
    guard_group.add_argument("--changed", action="append")
    guard_group.add_argument("--all", action="store_true")
    select_parser = commands.add_parser("select", help="rank deterministic and lexical antibody candidates")
    select_parser.add_argument("--directory", default=".")
    select_parser.add_argument("--changed", action="append", required=True)
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
    if args.command == "select":
        try:
            rankings = rank_repository(repository, args.changed)
        except SelectionError as error:
            print(f"Aegis select: {error}")
            return 1
        print(json.dumps([{"id": item.id, "score": item.score, "reason": item.reason} for item in rankings], sort_keys=True))
        return 0
    if args.command == "guard":
        result = guard(repository, ["*"] if args.all else args.changed)
        print(f"Aegis guard: {result}")
        return 0 if result == "pass" else 1
    if args.command == "approve":
        try:
            if args.github_repository and args.pull_number is None:
                parser.error("--pull-number is required with --github-repository")
            record = approve(
                repository,
                args.id,
                Path(args.github_fixture).resolve() if args.github_fixture else None,
                args.required_owner,
                args.github_repository,
                args.pull_number,
            )
            print(f"Aegis approval: verified {record.relative_to(repository)}")
        except ApprovalError as error:
            print(f"Aegis approval: {error}")
            return 1
        return 0
    if args.command == "prove":
        try:
            record = prove(repository, load_antibody(repository, args.id), Path(args.known_bad).resolve(), Path(args.alternate_bad).resolve(), args.control)
            print(f"Aegis proof: verified {record.relative_to(repository)}")
        except (AntibodyError, ProofError) as error:
            print(f"Aegis proof: {error}")
            return 1
        return 0
    if args.command == "antibody":
        try:
            if args.antibody_command == "create":
                record = create_antibody(repository, args.id, args.invariant, args.target, args.test, args.scope, args.proof_input)
                print(f"Created {record.relative_to(repository)}")
            else:
                print(explain_antibody(load_antibody(repository, args.id), proof_freshness(repository, args.id)))
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

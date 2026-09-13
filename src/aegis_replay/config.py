"""Strict parsing for repository-local Aegis configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigurationError(ValueError):
    """Configuration cannot be executed safely."""


SHELL_TOKENS = (";", "|", "&", ">", "<", "`", "$", "\n", "\r")
SUPPORTED_RUNNERS = frozenset({"command-junit", "gradle-junit", "pytest-junit", "jest-junit", "xcode-junit"})
ALLOWED_ENVIRONMENT = frozenset({"CI", "LANG", "LC_ALL", "TZ"})


@dataclass(frozen=True)
class Target:
    name: str
    command: tuple[str, ...]
    junit_xml: str
    environment: dict[str, str]
    directory: str
    scope: tuple[str, ...]


def load_target(config_path: Path, target_name: str | None) -> Target:
    try:
        document: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ConfigurationError(f"cannot read configuration: {error}") from error
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ConfigurationError("schema_version must be 1")
    targets = document.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ConfigurationError("targets must contain at least one target")
    selected = [item for item in targets if isinstance(item, dict) and item.get("name") == (target_name or "default")]
    if len(selected) != 1:
        raise ConfigurationError("target must name exactly one configured target")
    return _parse_target(selected[0])


def _parse_target(raw: dict[str, Any]) -> Target:
    if raw.get("runner") not in SUPPORTED_RUNNERS:
        raise ConfigurationError("runner must be a supported JUnit preset")
    name = raw.get("name")
    command = raw.get("command")
    junit_xml = raw.get("junit_xml")
    environment = raw.get("environment", {})
    directory = raw.get("directory", ".")
    scope = raw.get("scope", [])
    if not isinstance(name, str) or not name:
        raise ConfigurationError("target name must be non-empty")
    if not isinstance(command, list) or not command or not all(isinstance(value, str) and value for value in command):
        raise ConfigurationError("command must be a non-empty argv list")
    if any(token in value for value in command for token in SHELL_TOKENS):
        raise ConfigurationError("command must not contain shell syntax")
    if "/" in command[0] and ".." in Path(command[0]).parts:
        raise ConfigurationError("command path must not traverse outside repository")
    if not isinstance(junit_xml, str) or not _is_safe_relative_path(junit_xml):
        raise ConfigurationError("junit_xml must be a safe relative path")
    if not isinstance(directory, str) or not _is_safe_relative_path(directory):
        raise ConfigurationError("directory must be a safe relative path")
    if not isinstance(environment, dict) or any(
        not _is_allowed_environment(key) or not isinstance(value, str) for key, value in environment.items()
    ):
        raise ConfigurationError("environment contains disallowed values")
    if not isinstance(scope, list) or not all(isinstance(value, str) and _is_safe_relative_path(value) for value in scope):
        raise ConfigurationError("scope must contain safe relative paths")
    return Target(name, tuple(command), junit_xml, environment, directory, tuple(scope))


def _is_safe_relative_path(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def _is_allowed_environment(key: object) -> bool:
    return isinstance(key, str) and (key in ALLOWED_ENVIRONMENT or key.startswith("AEGIS_"))

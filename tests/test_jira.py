from __future__ import annotations

import json
from pathlib import Path

from aegis_replay.jira import capture, detect_key, linked_content_hash


def test_capture_keeps_only_sanitized_allowed_jira_fields(tmp_path: Path) -> None:
    payload = {"key": "APP-42", "fields": {"summary": "Restore sound", "description": "token=super-secret", "acceptance_criteria": "Audio returns", "issuetype": {"name": "Bug"}, "labels": ["audio"], "components": [{"name": "Service"}], "parent": {"name": "Epic"}, "comment": {"comments": ["never stored"]}, "attachment": [{"id": "never stored"}]}}
    path = capture(tmp_path, payload, "APP-42")
    stored = json.loads(path.read_text())
    assert stored["description"] == "[redacted]"
    assert stored["issue_type"] == "Bug"
    assert "comment" not in stored and "attachment" not in stored
    assert len(stored["content_sha256"]) == 64


def test_detect_key_uses_override_or_first_conventional_reference() -> None:
    assert detect_key("feature/APP-42-restore", "no ticket") == "APP-42"
    assert detect_key("nothing", override="OPS-9") == "OPS-9"


def test_capture_links_sanitized_ticket_content_to_an_antibody(tmp_path: Path) -> None:
    payload = {"key": "APP-42", "fields": {"summary": "Restore sound", "acceptance_criteria": "Audio returns"}}
    capture(tmp_path, payload, "APP-42", antibody_id="sound-restore")
    first = linked_content_hash(tmp_path, "sound-restore")
    changed = {"key": "APP-42", "fields": {"summary": "Restore sound", "acceptance_criteria": "Audio and DND return"}}
    capture(tmp_path, changed, "APP-42", antibody_id="sound-restore")
    assert linked_content_hash(tmp_path, "sound-restore") != first

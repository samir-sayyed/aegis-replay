import json

import pytest

from aegis_replay.manifest import write


def test_manifest_is_sanitized_immutable_and_reused_for_identical_inputs(tmp_path) -> None:
    first = write(tmp_path, {"commit_sha256": "a" * 64, "jira_sha256": "b" * 64}, [{"id": "a", "score": 1}], ["a"], "none", "recorded", "v1")
    second = write(tmp_path, {"jira_sha256": "b" * 64, "commit_sha256": "a" * 64}, [{"id": "a", "score": 1}], ["a"], "none", "recorded", "v1")
    assert first == second
    assert json.loads(first.read_text())["selected"] == ["a"]


def test_manifest_records_sanitized_execution_results(tmp_path) -> None:
    path = write(tmp_path, {"commit_sha256": "a" * 64}, [], ["a"], "none", "recorded", "v1", results=[{"id": "a", "result": "pass"}])
    assert json.loads(path.read_text())["results"] == [{"id": "a", "result": "pass"}]


def test_manifest_rejects_sensitive_or_raw_input_fields(tmp_path) -> None:
    with pytest.raises(ValueError):
        write(tmp_path, {"authorization_token": "no"}, [], [], "none", "m", "v1")

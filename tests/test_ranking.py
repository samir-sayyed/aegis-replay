from pathlib import Path

from aegis_replay.antibodies import create
from aegis_replay.jira import capture
from aegis_replay.ranking import rank
from aegis_replay.selection import rank_repository


def test_bm25_is_stable_explainable_and_preserves_deterministic_candidates() -> None:
    records = [
        {"id": "audio", "invariant": "audio restore stays pending", "jira": "sound recovery", "scope": ["service/audio.py"]},
        {"id": "network", "invariant": "retry network request", "jira": "http timeout", "scope": ["service/http.py"]},
    ]
    results = rank("audio restoration", records, {"network"})
    assert [item.id for item in results] == ["audio", "network"]
    assert results[0].score > results[1].score
    assert results[1].reason == "deterministic match"


def test_large_registry_keeps_top_twenty_and_all_deterministic_candidates() -> None:
    records = [{"id": f"item-{index:02}", "invariant": "audio restore" if index == 0 else "other", "jira": "", "scope": []} for index in range(51)]
    results = rank("audio", records, {"item-50"})
    assert len(results) == 21
    assert {item.id for item in results} >= {"item-00", "item-50"}


def test_repository_ranking_uses_sanitized_jira_intent_and_preserves_path_match(tmp_path: Path) -> None:
    (tmp_path / "aegis.yaml").write_text("schema_version: 1\ntargets:\n  - name: unit\n    runner: command-junit\n    command: ['python', '-m', 'pytest']\n    junit_xml: reports/junit.xml\n")
    digest = "a" * 64
    create(tmp_path, "audio", "Audio restore remains pending", "unit", ["suite#audio"], ["service/audio.py"], [f"source_revision={digest}"])
    create(tmp_path, "network", "Retry network request", "unit", ["suite#network"], ["service/http.py"], [f"source_revision={digest}"])
    capture(tmp_path, {"key": "APP-42", "fields": {"summary": "Audio recovery", "acceptance_criteria": "Sound returns"}}, "APP-42", antibody_id="audio")
    results = rank_repository(tmp_path, ["service/http.py"])
    assert {result.id for result in results} == {"audio", "network"}
    assert next(result for result in results if result.id == "network").reason == "deterministic match"

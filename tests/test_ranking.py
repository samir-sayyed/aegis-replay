from aegis_replay.ranking import rank


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

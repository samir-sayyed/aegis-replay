from aegis_replay.semantic import select


def test_semantic_selection_cannot_remove_deterministic_candidate(tmp_path) -> None:
    result = select(["a", "b"], {"a"}, {"commit": "1", "model": "recorded"}, lambda _: '{"selected":["b"],"uncertain":false}', tmp_path)
    assert result.ids == ("a", "b")
    assert not result.fallback


def test_invalid_or_uncertain_provider_response_runs_all_candidates() -> None:
    invalid = select(["a", "b"], {"a"}, {"commit": "1"}, lambda _: "not json")
    uncertain = select(["a", "b"], {"a"}, {"commit": "2"}, lambda _: '{"selected":["b"],"uncertain":true}')
    assert invalid.ids == ("a", "b") and invalid.fallback
    assert uncertain.ids == ("a", "b") and uncertain.fallback

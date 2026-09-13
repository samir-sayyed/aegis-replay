from aegis_replay.semantic import litellm_transport, select


def test_semantic_selection_cannot_remove_deterministic_candidate(tmp_path) -> None:
    result = select(["a", "b"], {"a"}, {"commit": "1", "model": "recorded"}, lambda _: '{"selected":["b"],"uncertain":false}', tmp_path)
    assert result.ids == ("a", "b")
    assert not result.fallback


def test_invalid_or_uncertain_provider_response_runs_all_candidates() -> None:
    invalid = select(["a", "b"], {"a"}, {"commit": "1"}, lambda _: "not json")
    uncertain = select(["a", "b"], {"a"}, {"commit": "2"}, lambda _: '{"selected":["b"],"uncertain":true}')
    assert invalid.ids == ("a", "b") and invalid.fallback
    assert uncertain.ids == ("a", "b") and uncertain.fallback


def test_litellm_transport_uses_zero_temperature_and_json_response() -> None:
    calls = []

    def request(endpoint, headers, body, timeout):
        calls.append((endpoint, headers, body, timeout))
        return {"choices": [{"message": {"content": '{"selected":["audio"],"uncertain":false}'}}]}

    transport = litellm_transport("https://llm.example/v1", "safe-model", "secret", request=request)
    assert transport({"paths": ["service/audio.py"]}) == '{"selected":["audio"],"uncertain":false}'
    endpoint, headers, body, timeout = calls[0]
    assert endpoint == "https://llm.example/v1/chat/completions"
    assert headers["Authorization"] == "Bearer secret"
    assert body["model"] == "safe-model" and body["temperature"] == 0
    assert timeout == 10

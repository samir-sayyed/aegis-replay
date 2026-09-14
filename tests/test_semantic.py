from aegis_replay.semantic import litellm_transport, select
from aegis_replay.selection import semantic_prompt


def test_semantic_selection_cannot_remove_deterministic_candidate(tmp_path) -> None:
    result = select(["a", "b"], {"a"}, {"commit": "1", "model": "recorded"}, lambda _: '{"selected":["b"],"uncertain":false}', tmp_path)
    assert result.ids == ("a", "b")
    assert not result.fallback


def test_invalid_or_uncertain_provider_response_runs_all_candidates() -> None:
    invalid = select(["a", "b"], {"a"}, {"commit": "1"}, lambda _: "not json")
    uncertain = select(["a", "b"], {"a"}, {"commit": "2"}, lambda _: '{"selected":["b"],"uncertain":true}')
    assert invalid.ids == ("a", "b") and invalid.fallback
    assert uncertain.ids == ("a", "b") and uncertain.fallback


def test_invalid_provider_payload_is_never_cached(tmp_path) -> None:
    result = select(["a"], set(), {"commit": "1"}, lambda _: '{"selected":["a"],"secret":"nope"}', tmp_path)
    assert result.fallback
    assert not list(tmp_path.glob("*.json"))


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


def test_cache_key_binds_candidates_and_semantic_prompt_is_bounded_and_redacted(tmp_path) -> None:
    first = select(["a"], set(), {"commit": "abc", "model": "one"}, lambda _: '{"selected":["a"],"uncertain":false}', tmp_path)
    second = select(["a", "b"], set(), {"commit": "abc", "model": "one"}, lambda _: '{"selected":["b"],"uncertain":false}', tmp_path)
    assert first.cache_key != second.cache_key and second.ids == ("b",)

    repository = tmp_path / "repo"
    (repository / ".aegis" / "antibodies").mkdir(parents=True)
    (repository / "aegis.yaml").write_text("schema_version: 1\ntargets: []\n")
    prompt = semantic_prompt(repository, ["src/a.py"], ["run"], "+ token=secret\n+ x = 1\n" * 4000, "a1b2c3d", "model")
    assert prompt["diff_hunks"].startswith("+ [redacted]")
    assert len(prompt["diff_hunks"]) == 6000

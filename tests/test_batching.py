import pytest

from aegis_replay.batching import attribute, plan
from aegis_replay.doctor import DoctorError, junit_identities


def test_compatible_tests_share_target_revision_with_exact_attribution() -> None:
    items = [{"id": "a", "target": "python", "revision": "1", "test": ("A", "one")}, {"id": "b", "target": "python", "revision": "1", "test": ("B", "two")}]
    assert len(plan(items)) == 1
    assert attribute(items, [("A", "one"), ("B", "two")]) == {"a": ("A", "one"), "b": ("B", "two")}


def test_ambiguous_or_missing_results_require_isolation() -> None:
    items = [{"id": "a", "target": "python", "revision": "1", "test": ("A", "one")}, {"id": "b", "target": "python", "revision": "1", "test": ("A", "one")}]
    with pytest.raises(ValueError):
        attribute(items, [("A", "one")])


def test_cross_stack_batches_preserve_every_antibody_identity() -> None:
    items = [
        {"id": "kotlin", "target": "kotlin-gradle", "revision": "1", "test": ("HealthTest", "healthy")},
        {"id": "swift", "target": "swift-xcode", "revision": "1", "test": ("StatusTests", "active")},
        {"id": "typescript", "target": "typescript-jest", "revision": "1", "test": ("feature.test", "preserves input")},
        {"id": "python", "target": "python-pytest", "revision": "1", "test": ("tests.test_greeting", "preserves_input_case")},
    ]
    batches = plan(items)
    assert len(batches) == 4
    for batch in batches.values():
        item = batch[0]
        assert attribute(batch, [item["test"]]) == {item["id"]: item["test"]}


def test_junit_attribution_rejects_duplicate_or_empty_identities(tmp_path) -> None:
    report = tmp_path / "result.xml"
    report.write_text('<testsuite><testcase classname="A" name="one"/><testcase classname="A" name="one"/></testsuite>')
    with pytest.raises(DoctorError):
        junit_identities(report)

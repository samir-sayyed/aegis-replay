import pytest

from aegis_replay.batching import attribute, plan


def test_compatible_tests_share_target_revision_with_exact_attribution() -> None:
    items = [{"id": "a", "target": "python", "revision": "1", "test": ("A", "one")}, {"id": "b", "target": "python", "revision": "1", "test": ("B", "two")}]
    assert len(plan(items)) == 1
    assert attribute(items, [("A", "one"), ("B", "two")]) == {"a": ("A", "one"), "b": ("B", "two")}


def test_ambiguous_or_missing_results_require_isolation() -> None:
    items = [{"id": "a", "target": "python", "revision": "1", "test": ("A", "one")}, {"id": "b", "target": "python", "revision": "1", "test": ("A", "one")}]
    with pytest.raises(ValueError):
        attribute(items, [("A", "one")])

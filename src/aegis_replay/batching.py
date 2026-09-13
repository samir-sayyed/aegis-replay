"""Safe batch planning and exact JUnit attribution."""

from __future__ import annotations

from collections import defaultdict


def plan(items: list[dict]) -> dict[tuple[str, str], list[dict]]:
    groups = defaultdict(list)
    for item in items:
        groups[(item["target"], item["revision"])].append(item)
    return dict(groups)


def attribute(items: list[dict], junit: list[tuple[str, str]]) -> dict[str, tuple[str, str]]:
    expected = {}
    for item in items:
        identity = tuple(item["test"])
        if identity in expected:
            raise ValueError("ambiguous expected JUnit identity; isolate execution")
        expected[identity] = item["id"]
    if len(junit) != len(set(junit)) or set(junit) != set(expected):
        raise ValueError("missing, duplicate, or ambiguous JUnit result; isolate execution")
    return {identifier: identity for identity, identifier in expected.items()}

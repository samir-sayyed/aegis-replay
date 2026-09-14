"""Explainable, deterministic BM25 ranking."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


WORDS = re.compile(r"[a-z0-9_]+")


@dataclass(frozen=True)
class Ranked:
    id: str
    score: float
    reason: str


def rank(query: str, records: list[dict], deterministic_ids: set[str], limit: bool = True) -> list[Ranked]:
    documents = {record["id"]: _words(" ".join([record.get("invariant", ""), record.get("jira", ""), " ".join(record.get("scope", []))])) for record in records}
    terms = _words(query)
    average = sum(len(value) for value in documents.values()) / max(len(documents), 1)
    results = []
    for identifier, document in documents.items():
        score = sum(_bm25(term, document, documents, average) for term in terms)
        reason = "deterministic match" if identifier in deterministic_ids else "BM25 lexical match"
        results.append(Ranked(identifier, round(score, 6), reason))
    results.sort(key=lambda item: (-item.score, item.id))
    if limit and len(results) > 50:
        retained = {item.id for item in results[:20]} | deterministic_ids
        results = [item for item in results if item.id in retained]
    return results


def _bm25(term: str, document: list[str], documents: dict[str, list[str]], average: float) -> float:
    frequency = document.count(term)
    if not frequency:
        return 0.0
    count = sum(term in values for values in documents.values())
    inverse = math.log(1 + (len(documents) - count + 0.5) / (count + 0.5))
    return inverse * frequency * 2.2 / (frequency + 1.2 * (1 - 0.75 + 0.75 * len(document) / max(average, 1)))


def _words(value: str) -> list[str]:
    return WORDS.findall(value.lower())

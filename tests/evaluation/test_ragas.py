"""RAGAS Evaluation Test Suite — Quality gates for RAG pipeline.

Uses the golden dataset to evaluate faithfulness, relevancy,
context precision, and context recall metrics.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from dataclasses import dataclass, field

import pytest


# ──────────────────────────────────────────────────
# Golden dataset loading
# ──────────────────────────────────────────────────

GOLDEN_PATH = Path(__file__).parent / "golden_dataset.json"


@dataclass
class GoldenItem:
    id: str
    question: str
    expected_answer: str
    relevant_sources: list[str]
    category: str
    difficulty: str


def load_golden_dataset() -> list[GoldenItem]:
    with open(GOLDEN_PATH) as f:
        data = json.load(f)
    return [GoldenItem(**q) for q in data["questions"]]


# ──────────────────────────────────────────────────
# Lightweight evaluation metrics (no external deps)
# ──────────────────────────────────────────────────

def cosine_similarity_words(text_a: str, text_b: str) -> float:
    """Word-overlap cosine similarity as a lightweight faithfulness proxy."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / math.sqrt(len(words_a) * len(words_b))


def answer_relevancy_score(question: str, answer: str) -> float:
    """Check if key question terms appear in the answer."""
    q_words = {w.lower().strip("?,.!") for w in question.split() if len(w) > 3}
    a_lower = answer.lower()
    if not q_words:
        return 1.0
    hits = sum(1 for w in q_words if w in a_lower)
    return hits / len(q_words)


def context_precision_score(expected_sources: list[str], retrieved_sources: list[str]) -> float:
    """Fraction of retrieved sources that are relevant."""
    if not retrieved_sources:
        return 0.0
    relevant = set(expected_sources)
    hits = sum(1 for s in retrieved_sources if s in relevant)
    return hits / len(retrieved_sources)


def context_recall_score(expected_sources: list[str], retrieved_sources: list[str]) -> float:
    """Fraction of expected sources that were retrieved."""
    if not expected_sources:
        return 1.0
    retrieved = set(retrieved_sources)
    hits = sum(1 for s in expected_sources if s in retrieved)
    return hits / len(expected_sources)


# ──────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────

class TestGoldenDataset:
    """Verify the golden dataset is well-formed."""

    def test_dataset_loads(self) -> None:
        items = load_golden_dataset()
        assert len(items) == 20

    def test_all_items_have_required_fields(self) -> None:
        items = load_golden_dataset()
        for item in items:
            assert item.id
            assert item.question
            assert item.expected_answer
            assert len(item.relevant_sources) >= 1
            assert item.category
            assert item.difficulty in ("simple", "medium", "complex")

    def test_unique_ids(self) -> None:
        items = load_golden_dataset()
        ids = [i.id for i in items]
        assert len(ids) == len(set(ids))

    def test_category_distribution(self) -> None:
        items = load_golden_dataset()
        categories = {i.category for i in items}
        # Should cover multiple categories
        assert len(categories) >= 4

    def test_difficulty_distribution(self) -> None:
        items = load_golden_dataset()
        difficulties = {i.difficulty for i in items}
        assert "simple" in difficulties
        assert "medium" in difficulties
        assert "complex" in difficulties


class TestMetricFunctions:
    """Verify the evaluation metric functions work correctly."""

    def test_cosine_similarity_identical(self) -> None:
        score = cosine_similarity_words("the cat sat on the mat", "the cat sat on the mat")
        assert score == pytest.approx(1.0)

    def test_cosine_similarity_disjoint(self) -> None:
        score = cosine_similarity_words("apple banana cherry", "dog elephant fox")
        assert score == 0.0

    def test_cosine_similarity_partial(self) -> None:
        score = cosine_similarity_words("data encryption security", "security protocol data")
        assert 0.3 < score < 1.0

    def test_answer_relevancy_full(self) -> None:
        score = answer_relevancy_score(
            "What encryption standard is used?",
            "The encryption standard used is AES-256."
        )
        assert score > 0.5

    def test_answer_relevancy_none(self) -> None:
        score = answer_relevancy_score(
            "What encryption standard is used?",
            "The sky is blue and water is wet."
        )
        assert score < 0.3

    def test_context_precision_perfect(self) -> None:
        score = context_precision_score(
            ["doc_a", "doc_b"],
            ["doc_a", "doc_b"]
        )
        assert score == 1.0

    def test_context_precision_partial(self) -> None:
        score = context_precision_score(
            ["doc_a", "doc_b"],
            ["doc_a", "doc_c", "doc_d"]
        )
        assert score == pytest.approx(1 / 3)

    def test_context_recall_perfect(self) -> None:
        score = context_recall_score(
            ["doc_a", "doc_b"],
            ["doc_a", "doc_b", "doc_c"]
        )
        assert score == 1.0

    def test_context_recall_partial(self) -> None:
        score = context_recall_score(
            ["doc_a", "doc_b"],
            ["doc_a"]
        )
        assert score == 0.5


class TestFaithfulnessBaseline:
    """Baseline faithfulness: expected answers should be self-consistent."""

    def test_expected_answers_are_coherent(self) -> None:
        """Each expected answer should have reasonable word overlap with its question."""
        items = load_golden_dataset()
        scores = []
        for item in items:
            score = cosine_similarity_words(item.question, item.expected_answer)
            scores.append(score)
        avg = sum(scores) / len(scores)
        # Golden Q&A pairs should have some overlap
        assert avg > 0.1, f"Average Q/A overlap too low: {avg:.3f}"

    def test_answer_relevancy_baseline(self) -> None:
        """Expected answers should be relevant to their questions."""
        items = load_golden_dataset()
        scores = []
        for item in items:
            score = answer_relevancy_score(item.question, item.expected_answer)
            scores.append(score)
        avg = sum(scores) / len(scores)
        assert avg > 0.3, f"Average relevancy too low: {avg:.3f}"

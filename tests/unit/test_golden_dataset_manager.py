"""Tests for GoldenDatasetManager — src/mlops/golden_dataset_manager.py."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.mlops.golden_dataset_manager import (
    ExpansionResult,
    GoldenDatasetManager,
    GoldenEntry,
    ProductionQA,
)


# ──────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────
def _good_qa(**overrides) -> ProductionQA:
    defaults = {
        "question": "What is the data retention policy?",
        "answer": "Data is retained for 7 years per EU AI Act requirements.",
        "contexts": ["doc-1 chunk-3"],
        "sources": ["compliance-policy.pdf"],
        "ragas_faithfulness": 0.97,
        "satisfaction_score": 0.95,
        "human_reviewed": True,
    }
    defaults.update(overrides)
    return ProductionQA(**defaults)


# ──────────────────────────────────────────────────
# Add Entry
# ──────────────────────────────────────────────────
class TestAddEntry:
    def test_add_single(self):
        mgr = GoldenDatasetManager()
        entry = GoldenEntry(question="Q1", ideal_answer="A1")
        mgr.add_entry(entry)
        assert mgr.count == 1

    def test_deduplicates_by_question(self):
        mgr = GoldenDatasetManager()
        mgr.add_entry(GoldenEntry(question="Same question", ideal_answer="A1"))
        mgr.add_entry(GoldenEntry(question="same question", ideal_answer="A2"))  # Case-insensitive dupe
        assert mgr.count == 1

    def test_different_questions_both_added(self):
        mgr = GoldenDatasetManager()
        mgr.add_entry(GoldenEntry(question="Q1", ideal_answer="A1"))
        mgr.add_entry(GoldenEntry(question="Q2", ideal_answer="A2"))
        assert mgr.count == 2


# ──────────────────────────────────────────────────
# Production → Golden
# ──────────────────────────────────────────────────
class TestAddFromProduction:
    def test_accepts_high_quality(self):
        mgr = GoldenDatasetManager()
        result = mgr.add_from_production([_good_qa()])
        assert result.entries_added == 1
        assert result.entries_rejected == 0

    def test_rejects_low_faithfulness(self):
        mgr = GoldenDatasetManager()
        result = mgr.add_from_production([_good_qa(ragas_faithfulness=0.80)])
        assert result.entries_added == 0
        assert result.reasons.get("low_faithfulness") == 1

    def test_rejects_low_satisfaction(self):
        mgr = GoldenDatasetManager()
        result = mgr.add_from_production([_good_qa(satisfaction_score=0.5)])
        assert result.entries_added == 0
        assert result.reasons.get("low_satisfaction") == 1

    def test_rejects_unreviewed(self):
        mgr = GoldenDatasetManager()
        result = mgr.add_from_production([_good_qa(human_reviewed=False)])
        assert result.entries_added == 0
        assert result.reasons.get("not_reviewed") == 1

    def test_rejects_empty_question(self):
        mgr = GoldenDatasetManager()
        result = mgr.add_from_production([_good_qa(question="")])
        assert result.entries_added == 0
        assert result.reasons.get("empty_content") == 1

    def test_rejects_empty_answer(self):
        mgr = GoldenDatasetManager()
        result = mgr.add_from_production([_good_qa(answer="")])
        assert result.entries_added == 0
        assert result.reasons.get("empty_content") == 1

    def test_deduplicates_against_existing(self):
        mgr = GoldenDatasetManager()
        mgr.add_entry(GoldenEntry(question="What is the data retention policy?", ideal_answer="Existing"))
        result = mgr.add_from_production([_good_qa()])
        assert result.entries_added == 0
        assert result.reasons.get("duplicate") == 1
        assert mgr.count == 1  # Still just the original

    def test_max_additions_respected(self):
        mgr = GoldenDatasetManager()
        candidates = [_good_qa(question=f"Q{i}") for i in range(10)]
        result = mgr.add_from_production(candidates, max_additions=3)
        assert result.entries_added == 3
        assert mgr.count == 3

    def test_expansion_history_tracked(self):
        mgr = GoldenDatasetManager()
        mgr.add_from_production([_good_qa()])
        mgr.add_from_production([_good_qa(question="Another?")])
        assert len(mgr.expansion_history) == 2

    def test_mixed_candidates(self):
        mgr = GoldenDatasetManager()
        candidates = [
            _good_qa(question="Good1"),
            _good_qa(question="Good2"),
            _good_qa(question="Bad1", ragas_faithfulness=0.50),
            _good_qa(question="Bad2", human_reviewed=False),
        ]
        result = mgr.add_from_production(candidates)
        assert result.entries_added == 2
        assert result.entries_rejected == 2
        assert result.candidates_evaluated == 4

    def test_skip_human_review_gate(self):
        mgr = GoldenDatasetManager(require_human_review=False)
        result = mgr.add_from_production([_good_qa(human_reviewed=False)])
        assert result.entries_added == 1


# ──────────────────────────────────────────────────
# Categories and Difficulties
# ──────────────────────────────────────────────────
class TestCategoriesAndDifficulties:
    def test_categories(self):
        mgr = GoldenDatasetManager()
        mgr.add_entry(GoldenEntry(question="Q1", category="security"))
        mgr.add_entry(GoldenEntry(question="Q2", category="security"))
        mgr.add_entry(GoldenEntry(question="Q3", category="compliance"))
        cats = mgr.get_categories()
        assert cats == {"security": 2, "compliance": 1}

    def test_difficulties(self):
        mgr = GoldenDatasetManager()
        mgr.add_entry(GoldenEntry(question="Q1", difficulty="easy"))
        mgr.add_entry(GoldenEntry(question="Q2", difficulty="hard"))
        diffs = mgr.get_difficulties()
        assert diffs == {"easy": 1, "hard": 1}


# ──────────────────────────────────────────────────
# JSON Export / Import
# ──────────────────────────────────────────────────
class TestJsonIO:
    def test_export_returns_valid_json(self):
        mgr = GoldenDatasetManager()
        mgr.add_entry(GoldenEntry(question="Q1", ideal_answer="A1"))
        json_str = mgr.export_json()
        data = json.loads(json_str)
        assert data["total_questions"] == 1
        assert len(data["questions"]) == 1

    def test_export_to_file(self, tmp_path):
        mgr = GoldenDatasetManager()
        mgr.add_entry(GoldenEntry(question="Q1", ideal_answer="A1"))
        path = str(tmp_path / "golden.json")
        mgr.export_json(path)
        assert Path(path).exists()
        data = json.loads(Path(path).read_text())
        assert data["total_questions"] == 1

    def test_load_from_json(self, tmp_path):
        data = {
            "questions": [
                {"question": "What is X?", "ideal_answer": "X is Y."},
                {"question": "How does Z work?", "expected_answer": "Z works by..."},
            ],
        }
        path = str(tmp_path / "input.json")
        Path(path).write_text(json.dumps(data))

        mgr = GoldenDatasetManager()
        loaded = mgr.load_from_json(path)
        assert loaded == 2
        assert mgr.count == 2

    def test_roundtrip(self, tmp_path):
        mgr1 = GoldenDatasetManager()
        mgr1.add_entry(GoldenEntry(question="Q1", ideal_answer="A1", category="test"))
        path = str(tmp_path / "roundtrip.json")
        mgr1.export_json(path)

        mgr2 = GoldenDatasetManager()
        mgr2.load_from_json(path)
        assert mgr2.count == 1
        assert mgr2.entries[0].question == "Q1"

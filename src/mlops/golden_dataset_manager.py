"""Golden Dataset Manager — Expand the evaluation dataset from production Q&A.

Identifies high-quality production query-answer pairs (faithfulness > 0.95,
satisfaction > 0.9, human-reviewed) and adds them to the golden dataset
for RAGAS evaluation. Supports JSON export with versioning metadata.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoldenEntry:
    """A single golden dataset entry for RAGAS evaluation."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    question: str = ""
    ideal_answer: str = ""
    contexts: list[str] = field(default_factory=list)
    relevant_sources: list[str] = field(default_factory=list)
    category: str = "general"
    difficulty: str = "medium"
    added_from: str = "manual"  # manual | production
    added_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductionQA:
    """A production query-answer pair that is a candidate for golden dataset."""

    question: str
    answer: str
    contexts: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    ragas_faithfulness: float = 0.0
    satisfaction_score: float = 0.0
    human_reviewed: bool = False
    category: str = "general"
    difficulty: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExpansionResult:
    """Result of a golden dataset expansion run."""

    candidates_evaluated: int
    entries_added: int
    entries_rejected: int
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    reasons: dict[str, int] = field(default_factory=dict)


# ──────────────────────────────────────────────────
# Quality thresholds (from Phase 6 spec §6.2)
# ──────────────────────────────────────────────────
_FAITHFULNESS_MIN = 0.95
_SATISFACTION_MIN = 0.9


class GoldenDatasetManager:
    """Manages the golden dataset for RAGAS evaluation.

    Usage::

        manager = GoldenDatasetManager()
        manager.load_from_json("tests/evaluation/golden_dataset.json")

        # Add from production
        result = manager.add_from_production([
            ProductionQA(question="...", answer="...", ragas_faithfulness=0.97, ...),
        ])

        # Export
        manager.export_json("tests/evaluation/golden_dataset.json")
    """

    def __init__(
        self,
        *,
        faithfulness_min: float = _FAITHFULNESS_MIN,
        satisfaction_min: float = _SATISFACTION_MIN,
        require_human_review: bool = True,
    ) -> None:
        self._entries: list[GoldenEntry] = []
        self._faithfulness_min = faithfulness_min
        self._satisfaction_min = satisfaction_min
        self._require_human_review = require_human_review
        self._expansion_history: list[ExpansionResult] = []

    @property
    def entries(self) -> list[GoldenEntry]:
        return list(self._entries)

    @property
    def count(self) -> int:
        return len(self._entries)

    @property
    def expansion_history(self) -> list[ExpansionResult]:
        return list(self._expansion_history)

    def add_entry(self, entry: GoldenEntry) -> None:
        """Add a single entry to the golden dataset."""
        # Deduplicate by question text
        for existing in self._entries:
            if existing.question.strip().lower() == entry.question.strip().lower():
                logger.debug("Duplicate question skipped: %s", entry.question[:50])
                return
        self._entries.append(entry)

    def add_from_production(
        self,
        candidates: list[ProductionQA],
        *,
        max_additions: int = 100,
    ) -> ExpansionResult:
        """Filter and add high-quality production Q&A to the golden dataset.

        Applies quality gates:
        - RAGAS faithfulness >= threshold (default 0.95)
        - Satisfaction score >= threshold (default 0.9)
        - Human reviewed (if required)

        Args:
            candidates: List of production Q&A pairs to evaluate.
            max_additions: Maximum entries to add in one run.

        Returns:
            ExpansionResult with counts and rejection reasons.
        """
        added = 0
        rejected = 0
        reasons: dict[str, int] = {}

        for qa in candidates:
            if added >= max_additions:
                break

            # Quality gates
            if qa.ragas_faithfulness < self._faithfulness_min:
                reasons["low_faithfulness"] = reasons.get("low_faithfulness", 0) + 1
                rejected += 1
                continue

            if qa.satisfaction_score < self._satisfaction_min:
                reasons["low_satisfaction"] = reasons.get("low_satisfaction", 0) + 1
                rejected += 1
                continue

            if self._require_human_review and not qa.human_reviewed:
                reasons["not_reviewed"] = reasons.get("not_reviewed", 0) + 1
                rejected += 1
                continue

            if not qa.question.strip() or not qa.answer.strip():
                reasons["empty_content"] = reasons.get("empty_content", 0) + 1
                rejected += 1
                continue

            entry = GoldenEntry(
                question=qa.question,
                ideal_answer=qa.answer,
                contexts=qa.contexts,
                relevant_sources=qa.sources,
                category=qa.category,
                difficulty=qa.difficulty,
                added_from="production",
                metadata={
                    "ragas_faithfulness": qa.ragas_faithfulness,
                    "satisfaction_score": qa.satisfaction_score,
                    **qa.metadata,
                },
            )

            # Deduplicate
            before = self.count
            self.add_entry(entry)
            if self.count > before:
                added += 1
            else:
                reasons["duplicate"] = reasons.get("duplicate", 0) + 1
                rejected += 1

        result = ExpansionResult(
            candidates_evaluated=len(candidates),
            entries_added=added,
            entries_rejected=rejected,
            reasons=reasons,
        )
        self._expansion_history.append(result)

        logger.info(
            "Golden dataset expansion: %d added, %d rejected (from %d candidates)",
            added,
            rejected,
            len(candidates),
        )
        return result

    def get_categories(self) -> dict[str, int]:
        """Count entries per category."""
        counts: dict[str, int] = {}
        for entry in self._entries:
            counts[entry.category] = counts.get(entry.category, 0) + 1
        return counts

    def get_difficulties(self) -> dict[str, int]:
        """Count entries per difficulty level."""
        counts: dict[str, int] = {}
        for entry in self._entries:
            counts[entry.difficulty] = counts.get(entry.difficulty, 0) + 1
        return counts

    def load_from_json(self, path: str) -> int:
        """Load golden dataset from a JSON file.

        Expected format::

            {"questions": [{"id": "...", "question": "...", ...}, ...]}

        Returns:
            Number of entries loaded.
        """
        with open(path) as f:
            data = json.load(f)

        loaded = 0
        for item in data.get("questions", []):
            entry = GoldenEntry(
                id=item.get("id", str(uuid.uuid4())),
                question=item.get("question", ""),
                ideal_answer=item.get("ideal_answer", item.get("expected_answer", "")),
                contexts=item.get("contexts", []),
                relevant_sources=item.get("relevant_sources", []),
                category=item.get("category", "general"),
                difficulty=item.get("difficulty", "medium"),
                added_from=item.get("added_from", "manual"),
            )
            self.add_entry(entry)
            loaded += 1

        logger.info("Loaded %d entries from %s", loaded, path)
        return loaded

    def export_json(self, path: str | None = None) -> str:
        """Export golden dataset as JSON.

        Args:
            path: If provided, write to file. Otherwise return JSON string.

        Returns:
            JSON string of the dataset.
        """
        data = {
            "version": datetime.now(timezone.utc).strftime("%Y%m%d"),
            "total_questions": self.count,
            "categories": self.get_categories(),
            "difficulties": self.get_difficulties(),
            "questions": [asdict(e) for e in self._entries],
        }
        json_str = json.dumps(data, indent=2)

        if path:
            with open(path, "w") as f:
                f.write(json_str)
            logger.info("Exported %d entries to %s", self.count, path)

        return json_str

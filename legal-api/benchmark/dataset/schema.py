"""
LegalBench-GH Dataset Schema
=============================

Pydantic models defining the benchmark test case structure, dataset
container, and loading utilities.
"""

import json
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class QuestionCategory(str, Enum):
    """Categories of legal questions in the benchmark."""
    CONSTITUTIONAL_FACTUAL = "constitutional_factual"
    CONSTITUTIONAL_INTERPRETIVE = "constitutional_interpretive"
    CASE_LAW_PRECEDENT = "case_law_precedent"
    PROCEDURAL = "procedural"
    ADVERSARIAL = "adversarial"


class Difficulty(str, Enum):
    """Difficulty levels for benchmark questions."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class BenchmarkQuestion(BaseModel):
    """A single benchmark question with gold-standard answer."""

    id: str = Field(
        description="Unique identifier, e.g. 'CONST-F-001' for constitutional factual #1"
    )
    category: QuestionCategory = Field(
        description="Question category for stratified evaluation"
    )
    difficulty: Difficulty = Field(
        description="Difficulty level as assessed by legal expert"
    )
    question: str = Field(
        description="The legal question to be answered"
    )
    gold_answer: str = Field(
        description="Lawyer-validated reference answer"
    )
    required_citations: list[str] = Field(
        default_factory=list,
        description="Expected legal citations, e.g. ['Article 21(1)(a)', 'Tuffuor v AG']"
    )
    source_document: str = Field(
        description="Source document the answer is grounded in"
    )
    retrieval_context: list[str] = Field(
        default_factory=list,
        description="Relevant context passages for RAG-based evaluation"
    )
    annotator: Optional[str] = Field(
        default=None,
        description="Name/ID of the legal expert who validated this question"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes about the question or expected answer"
    )


class BenchmarkDataset(BaseModel):
    """Container for the full LegalBench-GH benchmark dataset."""

    version: str = Field(default="0.1.0")
    description: str = Field(default="LegalBench-GH: Ghanaian Legal QA Benchmark")
    questions: list[BenchmarkQuestion] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.questions)

    def by_category(self, category: QuestionCategory) -> list[BenchmarkQuestion]:
        return [q for q in self.questions if q.category == category]

    def by_difficulty(self, difficulty: Difficulty) -> list[BenchmarkQuestion]:
        return [q for q in self.questions if q.difficulty == difficulty]

    def summary(self) -> dict:
        """Return a summary of the dataset composition."""
        summary = {"total": self.total, "by_category": {}, "by_difficulty": {}}
        for cat in QuestionCategory:
            count = len(self.by_category(cat))
            if count > 0:
                summary["by_category"][cat.value] = count
        for diff in Difficulty:
            count = len(self.by_difficulty(diff))
            if count > 0:
                summary["by_difficulty"][diff.value] = count
        return summary


def load_dataset(path: str | Path | None = None) -> BenchmarkDataset:
    """
    Load the LegalBench-GH dataset from a JSON file.

    Args:
        path: Path to the dataset JSON file.
              Defaults to benchmark/dataset/legalbench_gh.json.

    Returns:
        BenchmarkDataset with all questions loaded and validated.
    """
    if path is None:
        path = Path(__file__).parent / "legalbench_gh.json"
    else:
        path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Dataset not found at {path}")

    with open(path, "r") as f:
        data = json.load(f)

    return BenchmarkDataset(**data)

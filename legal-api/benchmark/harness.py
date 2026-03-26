"""
Evaluation Harness
==================

Main orchestrator that:
1. Loads the LegalBench-GH dataset
2. Runs each model configuration against all questions
3. Scores every answer on 7 metrics via DeepEval
4. Returns structured results for reporting

Usage:
    harness = EvaluationHarness()
    results = await harness.run(runners=[...])
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from deepeval.test_case import LLMTestCase

from benchmark.dataset.schema import (
    BenchmarkDataset,
    BenchmarkQuestion,
    QuestionCategory,
    load_dataset,
)
from benchmark.metrics.standard import get_standard_metrics
from benchmark.metrics.legal import get_legal_metrics
from benchmark.runners.base import ModelRunner, GenerationResult

logger = logging.getLogger(__name__)


@dataclass
class QuestionResult:
    """Result of evaluating a single question for a single runner."""
    question_id: str
    category: str
    difficulty: str
    question: str
    gold_answer: str
    model_answer: str
    latency_seconds: float
    scores: dict[str, float] = field(default_factory=dict)
    passed: dict[str, bool] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class RunnerResult:
    """Aggregated results for a single runner across all questions."""
    runner_name: str
    question_results: list[QuestionResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def avg_scores(self) -> dict[str, float]:
        """Average score for each metric across all questions."""
        if not self.question_results:
            return {}
        all_metrics = set()
        for qr in self.question_results:
            all_metrics.update(qr.scores.keys())

        averages = {}
        for metric in sorted(all_metrics):
            values = [
                qr.scores[metric]
                for qr in self.question_results
                if metric in qr.scores
            ]
            averages[metric] = sum(values) / len(values) if values else 0.0
        return averages

    @property
    def avg_latency(self) -> float:
        """Average generation latency in seconds."""
        latencies = [qr.latency_seconds for qr in self.question_results]
        return sum(latencies) / len(latencies) if latencies else 0.0

    @property
    def pass_rates(self) -> dict[str, float]:
        """Pass rate for each metric."""
        if not self.question_results:
            return {}
        all_metrics = set()
        for qr in self.question_results:
            all_metrics.update(qr.passed.keys())

        rates = {}
        for metric in sorted(all_metrics):
            passes = [
                qr.passed[metric]
                for qr in self.question_results
                if metric in qr.passed
            ]
            rates[metric] = sum(passes) / len(passes) if passes else 0.0
        return rates

    def by_category(self, category: str) -> dict[str, float]:
        """Average scores filtered by question category."""
        filtered = [qr for qr in self.question_results if qr.category == category]
        if not filtered:
            return {}
        all_metrics = set()
        for qr in filtered:
            all_metrics.update(qr.scores.keys())

        averages = {}
        for metric in sorted(all_metrics):
            values = [qr.scores[metric] for qr in filtered if metric in qr.scores]
            averages[metric] = sum(values) / len(values) if values else 0.0
        return averages


@dataclass
class BenchmarkResults:
    """Container for all runner results from a benchmark run."""
    runner_results: list[RunnerResult] = field(default_factory=list)
    dataset_version: str = ""
    dataset_size: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Serialise results to a dictionary."""
        return {
            "timestamp": self.timestamp,
            "dataset_version": self.dataset_version,
            "dataset_size": self.dataset_size,
            "runners": [
                {
                    "name": rr.runner_name,
                    "avg_scores": rr.avg_scores,
                    "avg_latency": rr.avg_latency,
                    "pass_rates": rr.pass_rates,
                    "question_count": len(rr.question_results),
                }
                for rr in self.runner_results
            ],
        }

    def save(self, path: str | Path):
        """Save results to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Results saved to {path}")


class EvaluationHarness:
    """
    Main evaluation orchestrator.

    Loads the dataset, runs model configurations, scores outputs,
    and collects structured results.
    """

    def __init__(
        self,
        dataset_path: str | Path | None = None,
        judge_model: str = "gpt-4o-mini",
        max_concurrent: int = 3,
    ):
        self.dataset = load_dataset(dataset_path)
        self.judge_model = judge_model
        self.max_concurrent = max_concurrent
        self._standard_metrics = get_standard_metrics(model=judge_model)
        self._legal_metrics = get_legal_metrics(model=judge_model)
        self._all_metrics = self._standard_metrics + self._legal_metrics

    async def evaluate_question(
        self,
        runner: ModelRunner,
        question: BenchmarkQuestion,
        use_context: bool = True,
    ) -> QuestionResult:
        """
        Run a single question through a runner and score the output.

        Args:
            runner: Model runner to generate the answer.
            question: Benchmark question with gold answer.
            use_context: Whether to provide retrieval context to the runner.

        Returns:
            QuestionResult with scores for all 7 metrics.
        """
        # Generate answer
        context = question.retrieval_context if use_context else None
        gen_result = await runner.generate_timed(
            question=question.question,
            context=context,
        )

        if gen_result.error:
            return QuestionResult(
                question_id=question.id,
                category=question.category.value,
                difficulty=question.difficulty.value,
                question=question.question,
                gold_answer=question.gold_answer,
                model_answer="",
                latency_seconds=gen_result.latency_seconds,
                error=gen_result.error,
            )

        # Build DeepEval test case
        test_case = LLMTestCase(
            input=question.question,
            actual_output=gen_result.answer,
            expected_output=question.gold_answer,
            retrieval_context=question.retrieval_context if question.retrieval_context else None,
        )

        # Score on all metrics
        scores = {}
        passed = {}
        for metric in self._all_metrics:
            try:
                metric.measure(test_case)
                metric_name = metric.name if hasattr(metric, 'name') else metric.__class__.__name__
                scores[metric_name] = metric.score
                passed[metric_name] = metric.score >= metric.threshold
            except Exception as e:
                metric_name = getattr(metric, 'name', metric.__class__.__name__)
                logger.warning(f"Metric {metric_name} failed for {question.id}: {e}")
                scores[metric_name] = 0.0
                passed[metric_name] = False

        return QuestionResult(
            question_id=question.id,
            category=question.category.value,
            difficulty=question.difficulty.value,
            question=question.question,
            gold_answer=question.gold_answer,
            model_answer=gen_result.answer,
            latency_seconds=gen_result.latency_seconds,
            scores=scores,
            passed=passed,
        )

    async def run_runner(
        self,
        runner: ModelRunner,
        questions: list[BenchmarkQuestion] | None = None,
        use_context: bool = True,
    ) -> RunnerResult:
        """
        Run all benchmark questions through a single runner.

        Args:
            runner: Model runner to evaluate.
            questions: Subset of questions to run (defaults to all).
            use_context: Whether to provide retrieval context.

        Returns:
            RunnerResult with scores for all questions.
        """
        questions = questions or self.dataset.questions
        logger.info(f"Running {runner.name} on {len(questions)} questions...")

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def _eval_with_semaphore(q: BenchmarkQuestion) -> QuestionResult:
            async with semaphore:
                return await self.evaluate_question(runner, q, use_context)

        tasks = [_eval_with_semaphore(q) for q in questions]
        results = await asyncio.gather(*tasks)

        runner_result = RunnerResult(
            runner_name=runner.name,
            question_results=list(results),
        )

        logger.info(
            f"[{runner.name}] Complete. "
            f"Avg scores: {runner_result.avg_scores} | "
            f"Avg latency: {runner_result.avg_latency:.2f}s"
        )

        return runner_result

    async def run(
        self,
        runners: list[ModelRunner],
        questions: list[BenchmarkQuestion] | None = None,
        use_context: bool = True,
    ) -> BenchmarkResults:
        """
        Run the full benchmark across multiple runners.

        Args:
            runners: List of model runners to evaluate.
            questions: Subset of questions (defaults to all).
            use_context: Whether to provide retrieval context.

        Returns:
            BenchmarkResults containing all runner results.
        """
        logger.info(
            f"Starting benchmark: {len(runners)} runners × "
            f"{len(questions or self.dataset.questions)} questions"
        )

        benchmark_results = BenchmarkResults(
            dataset_version=self.dataset.version,
            dataset_size=len(questions or self.dataset.questions),
        )

        for runner in runners:
            result = await self.run_runner(runner, questions, use_context)
            benchmark_results.runner_results.append(result)

        return benchmark_results

"""
Real-Time Evaluation Service for Ghana Legal AI
================================================

Runs DeepEval metrics asynchronously on each query and logs results to Opik.
Evaluations are non-blocking - user gets response immediately while evaluation
runs in background.

Usage:
    evaluator = RealTimeEvaluator()
    asyncio.create_task(evaluator.evaluate_and_log(...))
"""

import asyncio
from dataclasses import dataclass
from typing import Optional
import random

from loguru import logger

try:
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        FaithfulnessMetric,
        HallucinationMetric,
    )
    from deepeval.test_case import LLMTestCase
    DEEPEVAL_AVAILABLE = True
except ImportError:
    DEEPEVAL_AVAILABLE = False
    logger.warning("DeepEval not installed. Real-time evaluations disabled.")

from ghana_legal.config import settings


@dataclass
class EvaluationResult:
    """Results from real-time evaluation."""
    query: str
    response: str
    expert_id: str
    faithfulness_score: Optional[float] = None
    relevancy_score: Optional[float] = None
    hallucination_score: Optional[float] = None
    evaluation_error: Optional[str] = None
    
    @property
    def passed(self) -> bool:
        """Check if all metrics passed their thresholds."""
        if self.evaluation_error:
            return False
        
        thresholds = {
            "faithfulness": 0.7,
            "relevancy": 0.7,
            "hallucination": 0.5,  # Lower is better for hallucination
        }
        
        if self.faithfulness_score is not None and self.faithfulness_score < thresholds["faithfulness"]:
            return False
        if self.relevancy_score is not None and self.relevancy_score < thresholds["relevancy"]:
            return False
        if self.hallucination_score is not None and self.hallucination_score > thresholds["hallucination"]:
            return False
            
        return True
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "expert_id": self.expert_id,
            "faithfulness": self.faithfulness_score,
            "relevancy": self.relevancy_score,
            "hallucination": self.hallucination_score,
            "passed": self.passed,
            "error": self.evaluation_error,
        }


class RealTimeEvaluator:
    """
    Runs DeepEval metrics on responses asynchronously.
    
    Evaluations run in background threads to avoid blocking the response.
    Results are logged to Opik for observability.
    """
    
    def __init__(
        self,
        sample_rate: float = 1.0,
        enable_faithfulness: bool = True,
        enable_relevancy: bool = True,
        enable_hallucination: bool = True,
    ):
        """
        Initialize the evaluator.
        
        Args:
            sample_rate: Fraction of queries to evaluate (0.0-1.0). 
                        1.0 = all queries, 0.1 = 10% of queries.
            enable_faithfulness: Whether to run faithfulness metric.
            enable_relevancy: Whether to run answer relevancy metric.
            enable_hallucination: Whether to run hallucination metric.
        """
        self.sample_rate = sample_rate
        self.enable_faithfulness = enable_faithfulness
        self.enable_relevancy = enable_relevancy
        self.enable_hallucination = enable_hallucination
        
        if not DEEPEVAL_AVAILABLE:
            logger.warning("DeepEval not available. Evaluations will be skipped.")
    
    def should_evaluate(self) -> bool:
        """Determine if this query should be evaluated based on sample rate."""
        return random.random() < self.sample_rate
    
    async def evaluate_and_log(
        self,
        query: str,
        response: str,
        context: list[str],
        expert_id: str,
        trace_id: Optional[str] = None,
    ) -> EvaluationResult:
        """
        Evaluate a response and log results to Opik.
        
        This method runs asynchronously in the background.
        
        Args:
            query: The user's input query.
            response: The LLM's response.
            context: Retrieved context documents.
            expert_id: ID of the legal expert.
            trace_id: Optional Opik trace ID for linking.
            
        Returns:
            EvaluationResult with scores and pass/fail status.
        """
        if not DEEPEVAL_AVAILABLE:
            return EvaluationResult(
                query=query,
                response=response,
                expert_id=expert_id,
                evaluation_error="DeepEval not installed"
            )
        
        if not self.should_evaluate():
            logger.debug(f"Skipping evaluation for query (sample_rate={self.sample_rate})")
            return EvaluationResult(
                query=query,
                response=response,
                expert_id=expert_id,
                evaluation_error="Skipped due to sampling"
            )
        
        logger.info(f"Running real-time evaluation for expert: {expert_id}")
        
        try:
            # Run evaluation in thread pool to avoid blocking
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._run_evaluation,
                query,
                response,
                context,
                expert_id,
            )
            
            # Log to Opik
            await self._log_to_opik(result, trace_id)
            
            logger.info(
                f"Evaluation complete | expert={expert_id} | "
                f"faithfulness={result.faithfulness_score:.2f} | "
                f"relevancy={result.relevancy_score:.2f} | "
                f"passed={result.passed}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Evaluation failed: {str(e)}")
            return EvaluationResult(
                query=query,
                response=response,
                expert_id=expert_id,
                evaluation_error=str(e)
            )
    
    def _run_evaluation(
        self,
        query: str,
        response: str,
        context: list[str],
        expert_id: str,
    ) -> EvaluationResult:
        """
        Run DeepEval metrics synchronously (called from thread pool).
        """
        result = EvaluationResult(
            query=query,
            response=response,
            expert_id=expert_id,
        )
        
        # Create test case
        test_case = LLMTestCase(
            input=query,
            actual_output=response,
            retrieval_context=context if context else ["No context available"],
        )
        
        # Run faithfulness metric
        if self.enable_faithfulness:
            try:
                metric = FaithfulnessMetric(threshold=0.7)
                metric.measure(test_case)
                result.faithfulness_score = metric.score
            except Exception as e:
                logger.warning(f"Faithfulness metric failed: {e}")
                result.faithfulness_score = 0.0
        
        # Run relevancy metric
        if self.enable_relevancy:
            try:
                metric = AnswerRelevancyMetric(threshold=0.7)
                metric.measure(test_case)
                result.relevancy_score = metric.score
            except Exception as e:
                logger.warning(f"Relevancy metric failed: {e}")
                result.relevancy_score = 0.0
        
        # Run hallucination metric
        if self.enable_hallucination:
            try:
                # HallucinationMetric requires 'context' not 'retrieval_context'
                hallucination_case = LLMTestCase(
                    input=query,
                    actual_output=response,
                    context=context if context else ["No context available"],
                )
                metric = HallucinationMetric(threshold=0.5)
                metric.measure(hallucination_case)
                result.hallucination_score = metric.score
            except Exception as e:
                logger.warning(f"Hallucination metric failed: {e}")
                result.hallucination_score = 1.0  # Assume worst case
        
        return result
    
    async def _log_to_opik(
        self,
        result: EvaluationResult,
        trace_id: Optional[str] = None,
    ) -> None:
        """
        Log evaluation results to Opik.
        """
        try:
            import opik
            
            # Ensure project is set (reload settings if needed)
            client = opik.Opik()
            
            # Log metrics as feedback scores
            scores = []
            if result.faithfulness_score is not None:
                scores.append({
                    "name": "faithfulness",
                    "value": result.faithfulness_score,
                    "reason": "DeepEval Metric"
                })
            if result.relevancy_score is not None:
                scores.append({
                    "name": "relevancy", 
                    "value": result.relevancy_score,
                    "reason": "DeepEval Metric"
                })
            if result.hallucination_score is not None:
                scores.append({
                    "name": "hallucination",
                    "value": result.hallucination_score,
                    "reason": "DeepEval Metric"
                })
            
            if trace_id:
                # Link to existing trace
                for score in scores:
                    client.log_feedback_score(
                        trace_id=trace_id,
                        name=score["name"],
                        value=score["value"],
                        reason=score["reason"]
                    )
                logger.info(f"Logged {len(scores)} scores to existing Opik trace {trace_id}")
            else:
                # Create standalone trace
                trace = client.trace(
                    name=f"evaluation_{result.expert_id}",
                    input={"query": result.query},
                    output={"response": result.response},
                    metadata=result.to_dict(),
                    tags=["evaluation", "real-time"]
                )
                
                # Log feedback to this new trace
                for score in scores:
                    trace.log_feedback_score(
                        name=score["name"],
                        value=score["value"],
                        reason=score["reason"]
                    )
                
                logger.info(f"Created Opik trace: {trace.id} with scores: {scores}")
                
        except Exception as e:
            logger.error(f"Failed to log to Opik: {e}")


# Singleton instance
_evaluator: Optional[RealTimeEvaluator] = None


def get_evaluator() -> RealTimeEvaluator:
    """Get or create the singleton evaluator instance."""
    global _evaluator
    if _evaluator is None:
        _evaluator = RealTimeEvaluator(
            sample_rate=getattr(settings, 'EVAL_SAMPLE_RATE', 1.0),
        )
    return _evaluator

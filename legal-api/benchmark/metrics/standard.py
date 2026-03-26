"""
Standard RAG Metrics
====================

Wraps the 4 standard DeepEval metrics used for RAG quality evaluation:
- Answer Relevancy
- Faithfulness
- Contextual Precision
- Contextual Recall
"""

from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
)


# Default thresholds aligned with paper targets
STANDARD_THRESHOLDS = {
    "answer_relevancy": 0.85,
    "faithfulness": 0.80,
    "contextual_precision": 0.75,
    "contextual_recall": 0.70,
}


def get_standard_metrics(
    thresholds: dict[str, float] | None = None,
    model: str = "gpt-4o-mini",
) -> list:
    """
    Create the 4 standard RAG evaluation metrics.

    Args:
        thresholds: Override default thresholds per metric.
        model: OpenAI model to use as the LLM judge.

    Returns:
        List of configured DeepEval metric instances.
    """
    t = {**STANDARD_THRESHOLDS, **(thresholds or {})}

    return [
        AnswerRelevancyMetric(
            threshold=t["answer_relevancy"],
            model=model,
        ),
        FaithfulnessMetric(
            threshold=t["faithfulness"],
            model=model,
        ),
        ContextualPrecisionMetric(
            threshold=t["contextual_precision"],
            model=model,
        ),
        ContextualRecallMetric(
            threshold=t["contextual_recall"],
            model=model,
        ),
    ]

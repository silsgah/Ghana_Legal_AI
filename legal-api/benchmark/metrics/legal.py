"""
Legal-Specific Evaluation Metrics
==================================

3 domain-specific metrics implemented via DeepEval's GEval:
- Legal Accuracy: Are citations real and correct?
- Legal Relevance: Does the response address Ghanaian law specifically?
- Legal Authority: Does it respect court hierarchy and constitutional supremacy?
"""

from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams


# Default thresholds aligned with paper targets
LEGAL_THRESHOLDS = {
    "legal_accuracy": 0.90,
    "legal_relevance": 0.85,
    "legal_authority": 0.80,
}


def _legal_accuracy_metric(threshold: float, model: str) -> GEval:
    """
    Legal Accuracy: Evaluates whether cited articles, case names, and
    legal provisions actually exist and are correctly referenced.
    """
    return GEval(
        name="Legal Accuracy",
        criteria=(
            "Evaluate whether the response accurately cites legal sources. "
            "Check the following:\n"
            "1. Article numbers mentioned must correspond to real provisions "
            "in the 1992 Constitution of Ghana.\n"
            "2. Case names and citations (e.g., '[1980] GLR 637') must be "
            "real and correctly attributed.\n"
            "3. The legal principles stated must be accurate according to "
            "the retrieval context provided.\n"
            "4. No fabricated or hallucinated legal references should be present.\n"
            "5. If the response qualifies its answer or acknowledges uncertainty, "
            "this should be positively assessed rather than penalised."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
            LLMTestCaseParams.RETRIEVAL_CONTEXT,
        ],
        threshold=threshold,
        model=model,
    )


def _legal_relevance_metric(threshold: float, model: str) -> GEval:
    """
    Legal Relevance: Evaluates whether the response addresses the specific
    legal question within the Ghanaian jurisdiction, not foreign law.
    """
    return GEval(
        name="Legal Relevance",
        criteria=(
            "Evaluate whether the response is relevant to Ghanaian law "
            "specifically. Check the following:\n"
            "1. The response must address the question within the context "
            "of Ghana's legal system (not US, UK, or other jurisdictions).\n"
            "2. Legal terminology should be Ghana-specific (e.g., 'State "
            "Attorney' not 'District Attorney', 'High Court' not 'District Court').\n"
            "3. Constitutional references should be to the 1992 Constitution "
            "of Ghana, not constitutions of other nations.\n"
            "4. The response should demonstrate awareness of Ghana's mixed "
            "legal heritage (common law, customary law, statutory law).\n"
            "5. Generic legal answers that could apply to any jurisdiction "
            "should score lower than Ghana-specific answers."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        threshold=threshold,
        model=model,
    )


def _legal_authority_metric(threshold: float, model: str) -> GEval:
    """
    Legal Authority: Evaluates whether the response respects the hierarchy
    of legal sources and court decisions in Ghana.
    """
    return GEval(
        name="Legal Authority",
        criteria=(
            "Evaluate whether the response correctly respects the hierarchy "
            "of legal authority in Ghana. Check the following:\n"
            "1. The Constitution is treated as supreme over all other laws.\n"
            "2. Supreme Court decisions are treated as binding on all lower courts.\n"
            "3. Court of Appeal decisions are treated as binding on High Court "
            "and below, but not on the Supreme Court.\n"
            "4. Statutory law is treated as subordinate to the Constitution.\n"
            "5. Customary law is recognised but treated as subordinate to "
            "both the Constitution and statutory law.\n"
            "6. When citing multiple sources, higher authorities should be "
            "given precedence.\n"
            "7. The response should not elevate lower court decisions above "
            "higher court decisions or subordinate legislation above "
            "constitutional provisions."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.RETRIEVAL_CONTEXT,
        ],
        threshold=threshold,
        model=model,
    )


def get_legal_metrics(
    thresholds: dict[str, float] | None = None,
    model: str = "gpt-4o-mini",
) -> list[GEval]:
    """
    Create the 3 legal-specific evaluation metrics.

    Args:
        thresholds: Override default thresholds per metric.
        model: OpenAI model to use as the LLM judge.

    Returns:
        List of configured GEval metric instances.
    """
    t = {**LEGAL_THRESHOLDS, **(thresholds or {})}

    return [
        _legal_accuracy_metric(t["legal_accuracy"], model),
        _legal_relevance_metric(t["legal_relevance"], model),
        _legal_authority_metric(t["legal_authority"], model),
    ]

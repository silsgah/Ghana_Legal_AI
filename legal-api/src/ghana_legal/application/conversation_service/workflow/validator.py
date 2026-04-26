"""Server-side citation validator + confidence scorer.

Pure functions only — no I/O, no LLM calls. The orchestration (running the
repair loop, calling the answer chain) lives in nodes.validate_answer_node.

The four-priority anti-hallucination system enforces grounding here:
  P1  every Citation must reference a (case_id, paragraph_id) pair that was
      actually retrieved this turn.
  P2  every Claim must carry ≥1 citation; synthesis claims must span ≥2
      distinct case_ids; constitutional claims must cite a constitution chunk.
  P4  ConfidenceTier is derived from bound_ratio, distinct_cases, and
      min_similarity (rerank score from the retriever).
"""

from dataclasses import dataclass, field
from typing import Literal, Optional

from ghana_legal.config import settings
from ghana_legal.domain.legal_answer import LegalAnswer, ConfidenceTier


ViolationKind = Literal[
    "missing_citations",          # claim has zero citations
    "unbound_citation",           # cited (case_id, paragraph_id) not in retrieved set
    "synthesis_underspecified",   # kind=synthesis but <2 distinct case_ids cited
    "constitutional_misclassified",  # kind=constitutional but no constitution doc cited
]


@dataclass
class Violation:
    kind: ViolationKind
    detail: str
    claim_index: int


@dataclass
class ValidationResult:
    passed: bool
    violations: list[Violation] = field(default_factory=list)
    bound_ratio: float = 0.0       # bound_claims / total_claims
    distinct_cases: int = 0        # unique case_ids cited across bound claims
    min_similarity: float = 0.0    # min retrieval score across cited docs
    bound_claim_indices: list[int] = field(default_factory=list)


def validate(envelope: LegalAnswer, retrieved: list[dict]) -> ValidationResult:
    """Check that every claim's citations bind to a retrieved (case_id, paragraph_id)."""
    if not envelope.claims:
        # Empty claims is a legitimate "I don't know" / no-retrieval state, not
        # a violation. Confidence-tier scoring will mark it low/insufficient.
        return ValidationResult(passed=True)

    retrieved_index = {(d.get("case_id", ""), d.get("paragraph_id", "")): d for d in retrieved}

    violations: list[Violation] = []
    bound_indices: list[int] = []
    cited_cases: set[str] = set()
    cited_scores: list[float] = []

    for i, claim in enumerate(envelope.claims):
        if not claim.citations:
            violations.append(Violation(
                kind="missing_citations",
                detail=f"Claim {i} has no citations.",
                claim_index=i,
            ))
            continue

        unbound = []
        for cit in claim.citations:
            key = (cit.case_id, cit.paragraph_id)
            doc = retrieved_index.get(key)
            if doc is None:
                unbound.append(key)
            else:
                cited_cases.add(cit.case_id)
                score = doc.get("score")
                if score is not None:
                    cited_scores.append(float(score))

        if unbound:
            unbound_str = ", ".join(f"({cid}, {pid})" for cid, pid in unbound)
            violations.append(Violation(
                kind="unbound_citation",
                detail=f"Claim {i} cites unretrieved chunks: {unbound_str}.",
                claim_index=i,
            ))
            continue

        # Kind-specific structural checks (only run when all citations are bound).
        if claim.kind == "synthesis":
            distinct = len({c.case_id for c in claim.citations})
            if distinct < 2:
                violations.append(Violation(
                    kind="synthesis_underspecified",
                    detail=f"Claim {i} kind=synthesis but only {distinct} distinct case_id cited.",
                    claim_index=i,
                ))
                continue
        elif claim.kind == "constitutional":
            cited_doc_types = {
                retrieved_index[(c.case_id, c.paragraph_id)].get("document_type", "")
                for c in claim.citations
            }
            if "constitution" not in cited_doc_types:
                violations.append(Violation(
                    kind="constitutional_misclassified",
                    detail=f"Claim {i} kind=constitutional but no cited doc has document_type=constitution.",
                    claim_index=i,
                ))
                continue

        bound_indices.append(i)

    total = len(envelope.claims)
    bound_ratio = len(bound_indices) / total if total else 0.0
    return ValidationResult(
        passed=(len(violations) == 0),
        violations=violations,
        bound_ratio=bound_ratio,
        distinct_cases=len(cited_cases),
        min_similarity=min(cited_scores) if cited_scores else 0.0,
        bound_claim_indices=bound_indices,
    )


def build_repair_instruction(violations: list[Violation], retrieved: list[dict]) -> str:
    """Compose the corrective system message used for the one-shot repair attempt."""
    lines = ["VALIDATION FAILURE — your previous answer had the following grounding violations:"]
    for v in violations:
        lines.append(f"  • [{v.kind}] {v.detail}")
    lines.append("")
    lines.append("Available retrieved sources for this turn (you may cite ONLY these):")
    for d in retrieved:
        cid = d.get("case_id", "?")
        pid = d.get("paragraph_id", "?")
        title = d.get("case_title", "")
        lines.append(f"  • case_id={cid}  paragraph_id={pid}  ({title})")
    lines.append("")
    lines.append(
        "Re-emit the LegalAnswer envelope. Every Claim.citations entry must use "
        "(case_id, paragraph_id) values from the list above. If you cannot ground "
        "an assertion in the available sources, drop the claim from the envelope."
    )
    return "\n".join(lines)


def strip_unbound_claims(envelope: LegalAnswer, result: ValidationResult) -> LegalAnswer:
    """Return a copy of envelope with only claims whose citations all bound."""
    if not envelope.claims:
        return envelope
    bound_set = set(result.bound_claim_indices)
    kept = [c for i, c in enumerate(envelope.claims) if i in bound_set]
    return envelope.model_copy(update={"claims": kept})


def compute_confidence(result: ValidationResult, envelope: LegalAnswer) -> ConfidenceTier:
    """Derive the per-answer confidence tier from validator output.

    Tiers:
      high          bound_ratio == 1.0, distinct_cases == 1,
                    min_similarity ≥ CONFIDENCE_HIGH_SIMILARITY_FLOOR
      medium        bound_ratio == 1.0, distinct_cases ≥ 2 (synthesis)
      low           bound_ratio in [CONFIDENCE_LOW_BOUND_RATIO, 1.0)
                    OR min_similarity < 0.5
                    OR claims is empty but retrieval ran (unstructured prose)
      insufficient  bound_ratio < CONFIDENCE_LOW_BOUND_RATIO with non-empty claims
                    (i.e. the model attempted to cite and most attempts were invented)
                    OR claims is empty AND retrieval was not used

    Empty claims is intentionally NOT insufficient when retrieval ran — that
    case usually means the model produced grounded prose but didn't structure
    it into Claim objects, which is a generation issue, not invention. Marking
    it low surfaces a warning banner without hiding a legitimate answer.
    """
    n_claims = len(envelope.claims)
    if n_claims == 0:
        # No retrieval → no opportunity to ground → can't claim confidence either way.
        # With retrieval but no structured claims → likely the model wrote prose
        # without breaking it into Claim objects. Surface as low, not refuse.
        return "insufficient" if not envelope.retrieval_used else "low"

    if result.bound_ratio < settings.CONFIDENCE_LOW_BOUND_RATIO:
        return "insufficient"

    if result.bound_ratio < 1.0:
        return "low"

    if result.min_similarity < 0.5:
        return "low"

    if result.distinct_cases >= 2:
        return "medium"

    if result.min_similarity >= settings.CONFIDENCE_HIGH_SIMILARITY_FLOOR:
        return "high"

    return "low"

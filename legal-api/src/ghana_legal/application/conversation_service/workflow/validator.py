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

import re
from dataclasses import dataclass, field
from typing import Literal, Optional

from ghana_legal.config import settings
from ghana_legal.domain.legal_answer import LegalAnswer, ConfidenceTier


_NORMALIZE_RE = re.compile(r"[\s_\-\.]+")


def _normalize_id(value: str) -> str:
    """Strip punctuation, whitespace, and case for fuzzy ID matching.

    Catches the most common structuring-model drift: emitting
    "Constitution of Ghana 1992" instead of "Constitution_of_Ghana_1992",
    "Tuffuor v Attorney-General" instead of "Tuffuor_v_Attorney_General",
    or "p 3 c 2" instead of "p3.c2". Without normalization the validator
    flags these as unbound and the lawyer sees Low Confidence on a perfectly
    grounded answer.
    """
    if not value:
        return ""
    return _NORMALIZE_RE.sub("", value.lower())


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

    # Two indices: exact match and normalized fuzzy match. The fuzzy index is a
    # safety net for the structuring model emitting case_ids with formatting
    # drift ("Constitution of Ghana 1992" vs "Constitution_of_Ghana_1992").
    retrieved_index = {(d.get("case_id", ""), d.get("paragraph_id", "")): d for d in retrieved}
    fuzzy_index = {
        (_normalize_id(cid), _normalize_id(pid)): doc
        for (cid, pid), doc in retrieved_index.items()
    }

    def _resolve(cit_case_id: str, cit_paragraph_id: str) -> Optional[dict]:
        """Return the matching retrieved doc for a citation, or None if unbound.

        Tries exact match first, then falls back to normalized fuzzy match.
        """
        doc = retrieved_index.get((cit_case_id, cit_paragraph_id))
        if doc is not None:
            return doc
        return fuzzy_index.get((_normalize_id(cit_case_id), _normalize_id(cit_paragraph_id)))

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
        resolved_docs: list[dict] = []
        for cit in claim.citations:
            doc = _resolve(cit.case_id, cit.paragraph_id)
            if doc is None:
                unbound.append((cit.case_id, cit.paragraph_id))
            else:
                # Use the canonical case_id from the retrieved payload, not the
                # citation's possibly-drifted version, so distinct_cases is
                # counted correctly.
                cited_cases.add(doc.get("case_id", cit.case_id))
                resolved_docs.append(doc)
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
            # Use canonical IDs from resolved_docs so a citation that fuzzy-matched
            # to "Tuffuor_v_AG" doesn't get counted as a different case from one
            # that exact-matched to the same canonical ID.
            distinct = len({d.get("case_id", "") for d in resolved_docs})
            if distinct < 2:
                violations.append(Violation(
                    kind="synthesis_underspecified",
                    detail=f"Claim {i} kind=synthesis but only {distinct} distinct case_id cited.",
                    claim_index=i,
                ))
                continue
        elif claim.kind == "constitutional":
            cited_doc_types = {d.get("document_type", "") for d in resolved_docs}
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

    Tiers (post-PR 6 tuning):
      high          every claim bound 1:1 to a single retrieved case_id (direct match)
      medium        every claim bound, citations span ≥2 distinct case_ids (synthesis)
      low           some claims couldn't be bound (bound_ratio in [low_floor, 1.0))
                    OR claims is empty but retrieval ran (unstructured prose)
      insufficient  bound_ratio < CONFIDENCE_LOW_BOUND_RATIO with non-empty claims
                    (most claims invented citations) OR claims empty + no retrieval

    Cross-encoder/cosine similarity is intentionally NOT used in this calculation.
    Earlier versions checked min_similarity ≥ 0.7 for "high", but Voyage law-2
    cosine scores on this corpus typically land in 0.5–0.65 for legitimately
    matching documents — that gate caused real grounded answers to be tagged
    "low" and hide the green badge from the lawyer. Binding success is the
    meaningful signal: if the structure chain extracted a (case_id, paragraph_id)
    that exists in the retrieved set, the citation is valid regardless of how
    confident the embedder was. min_similarity is still recorded in
    ValidationResult for log-line diagnostics.
    """
    n_claims = len(envelope.claims)
    if n_claims == 0:
        # No retrieval → no opportunity to ground. With retrieval but no
        # structured claims, the model produced grounded prose without breaking
        # it into Claim objects (8b structuring miss). Surface as low.
        return "insufficient" if not envelope.retrieval_used else "low"

    if result.bound_ratio < settings.CONFIDENCE_LOW_BOUND_RATIO:
        return "insufficient"

    if result.bound_ratio < 1.0:
        return "low"

    # All claims fully bound from here on.
    if result.distinct_cases >= 2:
        return "medium"

    return "high"

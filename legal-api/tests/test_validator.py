"""Unit tests for the citation validator (PR 3) + confidence scorer (PR 4).

Pure-function tests — no LLM, no Qdrant, no I/O. Run with:
    pytest legal-api/tests/test_validator.py -v
"""

import pytest

from ghana_legal.application.conversation_service.workflow.validator import (
    Violation,
    compute_confidence,
    strip_unbound_claims,
    validate,
)
from ghana_legal.domain.legal_answer import Citation, Claim, LegalAnswer


def _retrieved(*triples):
    """Helper: build a retrieved-docs list from (case_id, paragraph_id, doc_type, score) tuples."""
    return [
        {
            "case_id": cid,
            "paragraph_id": pid,
            "document_type": dt,
            "score": score,
            "case_title": cid,
            "page_content": f"content of {cid}/{pid}",
        }
        for cid, pid, dt, score in triples
    ]


def _envelope(*claims):
    return LegalAnswer(human_text="x", retrieval_used=True, claims=list(claims))


# ───────────────────────── validate() ─────────────────────────


def test_empty_claims_passes():
    """No claims = no opportunity to invent. Validator returns passed=True."""
    result = validate(LegalAnswer(human_text=""), [])
    assert result.passed
    assert result.bound_ratio == 0.0
    assert result.violations == []


def test_single_direct_citation_binds():
    retrieved = _retrieved(("Tuffuor_v_AG", "p3.c2", "case_law", 0.85))
    env = _envelope(Claim(
        text="Tuffuor held X",
        kind="direct",
        citations=[Citation(case_id="Tuffuor_v_AG", paragraph_id="p3.c2")],
    ))
    result = validate(env, retrieved)
    assert result.passed
    assert result.bound_ratio == 1.0
    assert result.distinct_cases == 1
    assert result.min_similarity == 0.85


def test_unretrieved_citation_is_caught():
    """The core P1 + P2 enforcement — invented citations get flagged."""
    retrieved = _retrieved(("Real_Case", "p1.c0", "case_law", 0.7))
    env = _envelope(Claim(
        text="Made-up case held X",
        kind="direct",
        citations=[Citation(case_id="Imaginary_Case", paragraph_id="p9.c9")],
    ))
    result = validate(env, retrieved)
    assert not result.passed
    assert len(result.violations) == 1
    assert result.violations[0].kind == "unbound_citation"
    assert "Imaginary_Case" in result.violations[0].detail


def test_missing_citations_is_caught():
    env = _envelope(Claim(text="Bare assertion", kind="direct", citations=[]))
    result = validate(env, _retrieved())
    assert not result.passed
    assert result.violations[0].kind == "missing_citations"


def test_synthesis_with_two_distinct_cases_passes():
    retrieved = _retrieved(
        ("Case_A", "p1.c0", "case_law", 0.8),
        ("Case_B", "p2.c1", "case_law", 0.75),
    )
    env = _envelope(Claim(
        text="Across A and B...",
        kind="synthesis",
        citations=[
            Citation(case_id="Case_A", paragraph_id="p1.c0"),
            Citation(case_id="Case_B", paragraph_id="p2.c1"),
        ],
    ))
    result = validate(env, retrieved)
    assert result.passed
    assert result.distinct_cases == 2


def test_synthesis_with_only_one_case_fails():
    retrieved = _retrieved(("Case_A", "p1.c0", "case_law", 0.8))
    env = _envelope(Claim(
        text="Across cases...",
        kind="synthesis",
        citations=[Citation(case_id="Case_A", paragraph_id="p1.c0")],
    ))
    result = validate(env, retrieved)
    assert not result.passed
    assert result.violations[0].kind == "synthesis_underspecified"


def test_constitutional_must_cite_constitution_doc():
    retrieved = _retrieved(("Just_A_Case", "p1.c0", "case_law", 0.8))
    env = _envelope(Claim(
        text="Article 19 says...",
        kind="constitutional",
        citations=[Citation(case_id="Just_A_Case", paragraph_id="p1.c0")],
    ))
    result = validate(env, retrieved)
    assert not result.passed
    assert result.violations[0].kind == "constitutional_misclassified"


def test_constitutional_with_constitution_doc_passes():
    retrieved = _retrieved(("Constitution_of_Ghana_1992", "p1.c0", "constitution", 0.9))
    env = _envelope(Claim(
        text="Article 19 says...",
        kind="constitutional",
        citations=[Citation(case_id="Constitution_of_Ghana_1992", paragraph_id="p1.c0")],
    ))
    result = validate(env, retrieved)
    assert result.passed


def test_legacy_paragraph_id_format_binds():
    """Pre-PR 1 migrated points use 'legacy.cN' — must still bind."""
    retrieved = _retrieved(("Constitution_of_Ghana_1992", "legacy.c91", "constitution", 0.6))
    env = _envelope(Claim(
        text="Article 19...",
        kind="constitutional",
        citations=[Citation(case_id="Constitution_of_Ghana_1992", paragraph_id="legacy.c91")],
    ))
    result = validate(env, retrieved)
    assert result.passed


# ───────────────────────── strip_unbound_claims() ─────────────────────────


def test_strip_keeps_only_bound_claims():
    retrieved = _retrieved(("Real", "p1.c0", "case_law", 0.7))
    env = _envelope(
        Claim(text="bound", kind="direct", citations=[Citation(case_id="Real", paragraph_id="p1.c0")]),
        Claim(text="unbound", kind="direct", citations=[Citation(case_id="Fake", paragraph_id="p1.c0")]),
    )
    result = validate(env, retrieved)
    stripped = strip_unbound_claims(env, result)
    assert len(stripped.claims) == 1
    assert stripped.claims[0].text == "bound"


# ───────────────────────── compute_confidence() ─────────────────────────


def test_confidence_high_for_single_high_similarity_direct():
    retrieved = _retrieved(("Real", "p1.c0", "case_law", 0.85))
    env = _envelope(Claim(text="x", kind="direct", citations=[Citation(case_id="Real", paragraph_id="p1.c0")]))
    result = validate(env, retrieved)
    assert compute_confidence(result, env) == "high"


def test_confidence_medium_for_synthesis_across_two_cases():
    retrieved = _retrieved(
        ("A", "p1.c0", "case_law", 0.85),
        ("B", "p1.c0", "case_law", 0.85),
    )
    env = _envelope(Claim(
        text="x", kind="synthesis",
        citations=[Citation(case_id="A", paragraph_id="p1.c0"), Citation(case_id="B", paragraph_id="p1.c0")],
    ))
    result = validate(env, retrieved)
    assert compute_confidence(result, env) == "medium"


def test_confidence_low_when_similarity_below_floor():
    retrieved = _retrieved(("Real", "p1.c0", "case_law", 0.4))  # below 0.5
    env = _envelope(Claim(text="x", kind="direct", citations=[Citation(case_id="Real", paragraph_id="p1.c0")]))
    result = validate(env, retrieved)
    assert compute_confidence(result, env) == "low"


def test_confidence_insufficient_when_no_claims():
    env = LegalAnswer(human_text="I don't know", claims=[])
    result = validate(env, [])
    assert compute_confidence(result, env) == "insufficient"

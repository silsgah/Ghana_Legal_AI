"""Pydantic envelope for grounded legal answers.

The model emits a LegalAnswer via Groq's json_schema response format. The
server-side validator (added in PR 3) checks that every Citation references a
(case_id, paragraph_id) pair that was actually retrieved this turn — that is
how the four-priority anti-hallucination system enforces grounding.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


ClaimKind = Literal["direct", "synthesis", "constitutional"]
ConfidenceTier = Literal["high", "medium", "low", "insufficient"]


class Citation(BaseModel):
    """One bound reference to a retrieved corpus chunk."""

    case_id: str = Field(
        description=(
            "Stable identifier of the cited case. Must match a case_id present "
            "in the retrieved sources for this turn — invented values will be "
            "rejected by the validator."
        )
    )
    paragraph_id: str = Field(
        description=(
            "Paragraph identifier within the case (e.g. 'p3.c7' for post-PR1 "
            "ingests, or 'legacy.c91' for pre-migration corpus). Must match a "
            "paragraph_id present in the retrieved sources."
        )
    )
    case_title: Optional[str] = Field(
        default=None,
        description="Human-readable case title (e.g. 'Tuffuor v Attorney-General').",
    )
    court: Optional[str] = Field(default=None)
    year: Optional[int] = Field(default=None)


class Claim(BaseModel):
    """A single legal assertion plus the retrieved sources that ground it."""

    text: str = Field(description="The assertion in prose, as it appears in human_text.")
    kind: ClaimKind = Field(
        description=(
            "direct: bound to exactly one retrieved case. "
            "synthesis: derived from two or more retrieved cases. "
            "constitutional: cites a specific constitutional article from the corpus."
        )
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description=(
            "The (case_id, paragraph_id) pairs that ground this claim. Required "
            "for direct/constitutional kinds; synthesis claims must list ≥2 distinct cases."
        ),
    )


class LegalAnswer(BaseModel):
    """The complete grounded answer the model emits."""

    claims: list[Claim] = Field(
        default_factory=list,
        description="Every substantive legal assertion in human_text, broken out with citations.",
    )
    holding: Optional[str] = Field(
        default=None,
        description="The legal rule or holding that resolves the user's question, when applicable.",
    )
    principle: Optional[str] = Field(
        default=None,
        description="The broader legal principle the holding instantiates, when applicable.",
    )
    human_text: str = Field(
        description="The full prose answer (markdown) to render to the user.",
    )
    retrieval_used: bool = Field(
        default=False,
        description="Whether the model invoked retrieval before answering this turn.",
    )
    confidence: Optional[ConfidenceTier] = Field(
        default=None,
        description="Populated by the server-side validator in PR 4; leave None at generation time.",
    )

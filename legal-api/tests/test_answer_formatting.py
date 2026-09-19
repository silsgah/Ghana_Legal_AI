from ghana_legal.domain.answer_formatting import normalise_airac_markdown
from ghana_legal.application.conversation_service.workflow.retrieval_context import (
    MAX_CONTEXT_CHARS,
    MAX_CONTEXT_DOCUMENTS,
    build_retrieval_context,
)


def test_normalise_airac_escaped_pipe_table():
    source = """AIRAC Snapshot
\\| Area of Law | Constitutional law |
\\| --- | --- |
\\| Issues | Whether recusal is required. |
\\| Rules / Principles | Article 146 applies. |
\\| Analysis | The disclosed interest is material. |
\\| Conclusion | Recusal is required. |"""

    result = normalise_airac_markdown(source)

    assert "AIRAC Snapshot" not in result
    assert "\\|" not in result
    assert "| Area of Law" not in result
    assert result == """## Area of Law
Constitutional law

## Issues
Whether recusal is required.

## Rules / Principles
Article 146 applies.

## Analysis
The disclosed interest is material.

## Conclusion
Recusal is required."""


def test_normalise_airac_preserves_non_airac_tables():
    source = "| Court | Year |\n| --- | --- |\n| Supreme Court | 2024 |"

    assert normalise_airac_markdown(source) == source


class _Document:
    def __init__(self, index: int):
        self.page_content = f"Chunk {index} " + ("legal text " * 500)
        self.metadata = {
            "case_id": "RNAQ_2020_1",
            "paragraph_id": f"p{index}",
            "parties": "RNAQ v Republic",
        }


def test_retrieval_context_bounds_whole_judgment_fetches():
    sources, full_docs, context = build_retrieval_context(_Document(i) for i in range(500))

    assert len(full_docs) == 500
    assert len(sources) == MAX_CONTEXT_DOCUMENTS
    assert len(context) <= MAX_CONTEXT_CHARS
    assert full_docs[0]["in_llm_context"] is True
    assert full_docs[-1]["in_llm_context"] is True

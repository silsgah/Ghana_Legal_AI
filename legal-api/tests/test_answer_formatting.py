from ghana_legal.domain.answer_formatting import normalise_airac_markdown


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

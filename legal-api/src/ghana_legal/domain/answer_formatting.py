"""Deterministic presentation safeguards for user-visible legal answers."""

import re


_AIRAC_HEADINGS = {
    "area of law": "Area of Law",
    "issues": "Issues",
    "rules / principles": "Rules / Principles",
    "rules/principles": "Rules / Principles",
    "analysis": "Analysis",
    "conclusion": "Conclusion",
}


def normalise_airac_markdown(text: str) -> str:
    """Convert an accidental AIRAC Markdown table into readable legal prose.

    The answer model is instructed not to create tables, but this guard keeps a
    model lapse from reaching the chat as literal ``|`` / ``\\|`` markup.
    It intentionally transforms only tables whose row labels are AIRAC fields;
    any other Markdown table is left unchanged.
    """
    if not text:
        return text

    text = re.sub(r"(?im)^\s*#{0,6}\s*AIRAC\s+Snapshot\s*$\n?", "", text)
    lines = text.splitlines()
    output: list[str] = []
    index = 0

    while index < len(lines):
        row = _parse_table_row(lines[index])
        if row and _normalise_label(row[0]) in _AIRAC_HEADINGS:
            rows: list[tuple[str, str]] = []
            while index < len(lines):
                candidate = _parse_table_row(lines[index])
                if not candidate:
                    break
                if _is_separator_row(candidate):
                    index += 1
                    continue
                label = _normalise_label(candidate[0])
                if label not in _AIRAC_HEADINGS:
                    break
                rows.append((_AIRAC_HEADINGS[label], candidate[1]))
                index += 1

            if rows:
                if output and output[-1].strip():
                    output.append("")
                for heading, body in rows:
                    body = re.sub(r"(?i)<br\s*/?>", "\n", body).strip()
                    output.extend((f"## {heading}", body, ""))
                continue

        output.append(lines[index])
        index += 1

    return "\n".join(output).strip()


def _parse_table_row(line: str) -> tuple[str, str] | None:
    """Return a two-column table row, including the escaped-pipe variant."""
    cleaned = line.strip().replace("\\|", "|")
    if not cleaned.startswith("|"):
        return None
    cells = [cell.strip() for cell in cleaned.strip("|").split("|")]
    if len(cells) != 2:
        return None
    return cells[0], cells[1]


def _normalise_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().lower())


def _is_separator_row(row: tuple[str, str]) -> bool:
    return all(re.fullmatch(r"[:\-\s]+", cell) for cell in row)

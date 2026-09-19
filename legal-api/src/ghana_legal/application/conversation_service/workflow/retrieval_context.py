"""Bound retrieved text before it is included in an LLM conversation."""

from __future__ import annotations

from typing import Any, Iterable


# A full judgment may have hundreds of chunks.  These limits keep the answer
# request comfortably below provider context limits while retaining excerpts
# from throughout the judgment (opening, facts, reasoning and disposition).
MAX_CONTEXT_DOCUMENTS = 32
MAX_CONTEXT_CHARS = 48_000
MAX_DOCUMENT_CHARS = 1_800
_CONTEXT_SEPARATOR = "\n\n---\n\n"


def build_retrieval_context(docs: Iterable[Any]) -> tuple[list[dict], list[dict], str]:
    """Return UI sources, validator metadata, and a bounded LLM context.

    ``full_docs`` retains metadata for every retrieved chunk so citation
    validation remains faithful to retrieval. The LLM receives only a balanced
    selection of excerpts, which prevents a whole-case fetch from overflowing
    a model's ``messages`` limit.
    """
    documents = list(docs)
    full_docs: list[dict] = []
    entries: list[tuple[int, dict, str]] = []

    for index, doc in enumerate(documents, 1):
        meta = getattr(doc, "metadata", None) or {}
        title = (
            meta.get("parties")
            or meta.get("filename", "").replace(".pdf", "").replace("_", " ")
        ).strip()
        item = {
            "title": title,
            "court": meta.get("court", ""),
            "year": str(meta.get("year", "")),
            "document_type": meta.get("document_type", ""),
            "case_id": meta.get("case_id", ""),
            "paragraph_id": meta.get("paragraph_id", ""),
        }
        full_docs.append({
            **item,
            "case_title": title,
            "paragraph_hash": meta.get("paragraph_hash", ""),
            "score": meta.get("score"),
            "page_content": getattr(doc, "page_content", ""),
        })
        content = meta.get("parent_content") or getattr(doc, "page_content", "")
        entries.append((index, item, content))

    selected = _evenly_spaced(entries, MAX_CONTEXT_DOCUMENTS)
    selected_indexes = {index for index, _, _ in selected}
    for index, document in enumerate(full_docs, 1):
        document["in_llm_context"] = index in selected_indexes
    sources = [item for _, item, _ in selected]
    context_parts: list[str] = []
    remaining = MAX_CONTEXT_CHARS

    for original_index, item, content in selected:
        if remaining <= 0:
            break
        header_parts = [str(value) for value in (item["title"], item["court"], item["year"]) if value]
        header = " | ".join(header_parts) if header_parts else f"Source {original_index}"
        prefix = f"[Source {original_index}: {header}]\n"
        excerpt_limit = min(MAX_DOCUMENT_CHARS, remaining - len(prefix))
        if excerpt_limit <= 0:
            break
        excerpt = _truncate(content, excerpt_limit)
        part = f"{prefix}{excerpt}"
        context_parts.append(part)
        remaining -= len(part) + len(_CONTEXT_SEPARATOR)

    return sources, full_docs, _CONTEXT_SEPARATOR.join(context_parts)


def _evenly_spaced(items: list[tuple[int, dict, str]], limit: int) -> list[tuple[int, dict, str]]:
    if len(items) <= limit:
        return items
    positions = {round(i * (len(items) - 1) / (limit - 1)) for i in range(limit)}
    return [items[position] for position in sorted(positions)]


def _truncate(content: str, limit: int) -> str:
    content = content.strip()
    if len(content) <= limit:
        return content
    suffix = "\n[Excerpt truncated for context limit]"
    text_limit = max(0, limit - len(suffix))
    boundary = content.rfind(" ", 0, text_limit)
    if boundary < text_limit // 2:
        boundary = text_limit
    return f"{content[:boundary].rstrip()}{suffix}"

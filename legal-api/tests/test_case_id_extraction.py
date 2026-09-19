from ghana_legal.application.rag.qdrant_retriever import _extract_case_id_from_query


def test_extracts_plain_case_citation_with_narrow_no_break_spaces():
    assert _extract_case_id_from_query(
        "Provide details on this case GHASC\u202f2005\u202f9 (Supreme Court of Ghana, 2005)"
    ) == "GHASC_2005_9"


def test_extracts_plain_case_citation_with_normal_spaces():
    assert _extract_case_id_from_query("Tell me about GHASC 2005 9") == "GHASC_2005_9"

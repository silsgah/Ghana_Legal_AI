"""Legal-specific Qdrant Cloud retriever with hybrid search and reranking capabilities.

Drop-in replacement for ChromaDB retriever, using Qdrant Cloud for production vector search.
"""

import os
import re
from typing import List, Optional

from langchain_core.documents import Document
from loguru import logger
from sentence_transformers import CrossEncoder
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
)

from ghana_legal.config import settings

_qdrant_retriever_instance = None


# Allow up to 4 intervening words (case names, "the", etc.) between the
# verb/keyword and the noun ("case"/"judgment"/etc.) so phrases like
# "analyze the Mensah case" or "summarize the Tuffuor judgment" trigger.
_NOUN = r"(?:case|judgment|judgement|ruling|decision|opinion)"
_GAP = r"(?:\s+\w+){0,4}"

_FULL_JUDGMENT_INTENT_RE = re.compile(
    r"\b("
    rf"(?:full|entire|complete|whole){_GAP}\s+{_NOUN}"
    rf"|summari[sz]e{_GAP}\s+{_NOUN}"
    rf"|summary\s+of{_GAP}\s+{_NOUN}"
    rf"|details?\s+of{_GAP}\s+{_NOUN}"
    rf"|analy[sz]e{_GAP}\s+{_NOUN}"
    rf"|analysis\s+of{_GAP}\s+{_NOUN}"
    rf"|outcome\s+of{_GAP}\s+{_NOUN}"
    rf"|brief\s+(?:on|me\s+on){_GAP}\s+{_NOUN}"
    rf"|explain\s+(?:the\s+)?{_NOUN}"
    rf"|review\s+(?:the\s+)?{_NOUN}"
    rf"|outline\s+(?:the\s+)?{_NOUN}"
    rf"|breakdown\s+of{_GAP}\s+{_NOUN}"
    r"|walk\s+me\s+through"
    r"|what\s+happened\s+in"
    r"|why\s+did\s+the\s+court"
    r"|what\s+did\s+the\s+court\s+(?:hold|say|rule|decide|find|conclude)"
    r"|how\s+did\s+the\s+court\s+(?:rule|decide|hold|reason)"
    r"|facts\s+(?:of|in)\s+(?:the\s+)?case"
    r"|background\s+(?:of|to|in)\s+(?:the\s+)?case"
    r"|(?:ratio\s+decidendi|holding|reasoning|disposition|decision)\s+(?:in|of)"
    r"|tell\s+me\s+(?:about|everything\s+about)\s+"
    r")\b",
    re.IGNORECASE,
)

# Proper-noun form: "summarize Mensah", "analyze Tuffuor", "brief on Yeboah".
# Case-sensitive (no IGNORECASE) — the capitalised second word IS the signal
# that the user is naming a specific case, not asking a generic question.
_VERB_PROPERNOUN_RE = re.compile(
    r"\b(?:[Ss]ummari[sz]e|[Aa]naly[sz]e|[Ee]xplain|[Rr]eview|[Oo]utline|"
    r"[Bb]rief\s+(?:on|me\s+on))\s+(?:the\s+)?[A-Z][A-Za-z'\-\.]{2,}"
)

# Case-name pattern "Party A v Party B". Party halves stay case-sensitive
# (must START with an uppercase letter — the proper-noun anchor). The
# separator "v / vs / versus" uses an inline (?i:...) case-insensitive
# group so all-caps Ghanaian formal style ("X VS Y" or "X VERSUS Y") fires.
_CASE_NAME_RE = re.compile(
    r"\b[A-Z][A-Za-z'\-\.&]{1,40}"
    r"(?:\s+[A-Za-z'\-\.&]{1,40}){0,4}"
    r"\s+(?i:v|vs|versus|v\.|vs\.)\s+"
    r"[A-Z][A-Za-z'\-\.&]{1,40}"
    r"(?:\s+[A-Za-z'\-\.&]{1,40}){0,4}\b"
)

# Definitional / principle-only queries — even if the embeddings cluster on a
# single case, the user wants the principle, not the full judgment. Used to
# gate the implicit case-summary trigger below.
_DEFINITIONAL_PREFIX_RE = re.compile(
    r"^\s*("
    r"what\s+is|what\s+are|what\s+constitutes|what\s+does\s+\w+\s+mean"
    r"|define|definition\s+of|meaning\s+of"
    r"|explain\s+(?:the\s+)?(?:meaning|concept|principle|doctrine|notion)"
    r"|how\s+does\s+\w+\s+(?:work|operate|apply)"
    r"|can\s+(?:a|an|the)\s+\w+\s+\w+"
    r"|when\s+(?:can|does|is)"
    r")\b",
    re.IGNORECASE,
)

_PARAGRAPH_ID_TAIL_RE = re.compile(r"\.c(\d+)$")

# Citation → canonical case_id shortcut. Catches both the bracketed Ghanaian
# style ("[2022] GHACC 316", "(2020) GHACA 10") and the canonical form
# ("GHACC_2022_316") that admin tooling sometimes pastes verbatim. Bare-citation
# queries embed poorly (almost no semantic content), so when one is present we
# bypass vector search and pull the case by case_id directly.
_CITATION_BRACKET_RE = re.compile(
    r"[\[\(](\d{4})[\]\)]\s*(GHA[A-Z]{2,4})\s+(\d+)", re.IGNORECASE
)
_CASE_ID_CANONICAL_RE = re.compile(r"\b(GHA[A-Z]{2,4})_(\d{4})_(\d+)\b", re.IGNORECASE)


def _extract_case_id_from_query(query: str) -> Optional[str]:
    """Return a canonical case_id if the query names one, else None."""
    m = _CASE_ID_CANONICAL_RE.search(query)
    if m:
        court, year, num = m.groups()
        return f"{court.upper()}_{year}_{num}"
    m = _CITATION_BRACKET_RE.search(query)
    if m:
        year, court, num = m.groups()
        return f"{court.upper()}_{year}_{num}"
    return None

# (b) Implicit case-summary trigger: top vector hit score ≥ this floor.
# Voyage-law-2 cosine scores typically run 0.5–0.85 for relevant matches;
# 0.55 separates "the embeddings are confident this is THE case" from
# "the embeddings are guessing across several related cases."
_IMPLICIT_CASE_SCORE_FLOOR = 0.55
_IMPLICIT_CASE_MIN_WORDS = 5


def _detect_full_judgment_intent(query: str) -> bool:
    """True when the user is asking for the full judgment / coverage of a case.

    Three signals (any one is sufficient):
      (1) case-name pattern "X v Y" in the query
      (2) "<verb> <ProperNoun>" pattern — "summarize Mensah", "analyze Tuffuor"
      (3) coverage keywords (full judgment, summarize the case, facts of,
          holding in, ratio decidendi of, walk me through, what happened in,
          what did the court hold, brief on, etc.)
    """
    if not query:
        return False
    if _CASE_NAME_RE.search(query):
        return True
    if _VERB_PROPERNOUN_RE.search(query):
        return True
    return bool(_FULL_JUDGMENT_INTENT_RE.search(query))


def _detect_implicit_case_intent(
    query: str, vector_hits: List[Document]
) -> Optional[str]:
    """Detect "the user is clearly asking about ONE specific case" without keywords.

    Fires when:
      * query is ≥5 words and does NOT start with a definitional prefix
        ("what is...", "define...", "how does X work", etc.)
      * top vector hit score ≥ _IMPLICIT_CASE_SCORE_FLOOR (0.55)
      * ≥2 of the top 3 hits share a case_id AND that case is case_law

    Returns the dominant case_id, or None if no implicit signal.

    Rationale: when the embeddings pull a single case to the top with high
    confidence and the query isn't a definitional/principle question, the
    user is almost certainly asking about that case — even if they didn't
    use the literal phrase "full judgment". Without this, queries like
    "What happened in Mensah?" or "How did the court rule there?" fall
    through to default retrieval and get only k=10 chunks of a 60-chunk case.
    """
    if not query or not vector_hits:
        return None
    if len(query.split()) < _IMPLICIT_CASE_MIN_WORDS:
        return None
    if _DEFINITIONAL_PREFIX_RE.match(query):
        return None

    top_score = (vector_hits[0].metadata or {}).get("score")
    if top_score is None or float(top_score) < _IMPLICIT_CASE_SCORE_FLOOR:
        return None

    from collections import Counter
    top3 = vector_hits[:3]
    case_counts: Counter = Counter()
    case_doc_types: dict[str, str] = {}
    for doc in top3:
        meta = doc.metadata or {}
        cid = meta.get("case_id", "")
        if cid:
            case_counts[cid] += 1
            case_doc_types[cid] = meta.get("document_type", "")

    for cid, count in case_counts.most_common(1):
        if count >= 2 and case_doc_types.get(cid) == "case_law":
            return cid
    return None


def _order_by_document_position(docs: List[Document]) -> List[Document]:
    """Sort docs by (case_id, page_number, paragraph_chunk_idx, chunk_index).

    After case-aware fetch or post-rerank truncation, the chunks come back in
    score order — disposition before facts, holding before issues. That breaks
    narrative flow for the LLM. Re-sorting by document position restores
    facts → reasoning → holding so the answer reads coherently.
    """
    def _key(doc: Document):
        meta = doc.metadata or {}
        case_id = meta.get("case_id", "")

        page = meta.get("page_number") or 0
        try:
            page = int(page)
        except (TypeError, ValueError):
            page = 0

        pid = str(meta.get("paragraph_id", ""))
        match = _PARAGRAPH_ID_TAIL_RE.search(pid)
        chunk_idx = int(match.group(1)) if match else 0

        global_idx = meta.get("chunk_index") or 0
        try:
            global_idx = int(global_idx)
        except (TypeError, ValueError):
            global_idx = 0

        return (case_id, page, chunk_idx, global_idx)

    return sorted(docs, key=_key)


class LegalQdrantRetriever:
    """Legal-specific retriever using Qdrant Cloud with hybrid search and reranking."""

    def __init__(
        self,
        collection_name: str = "legal_docs",
        embedding_model_id: str = "voyage-law-2",
        k: int = 3,
        device: str = "cpu",
        use_reranker: bool = True,
    ):
        from ghana_legal.application.rag.embeddings import get_embedding_model

        self.k = k
        self.use_reranker = use_reranker
        self.collection_name = collection_name

        try:
            # Initialize Qdrant Cloud client
            qdrant_url = os.getenv("QDRANT_URL", "")
            qdrant_api_key = os.getenv("QDRANT_API_KEY", "")

            if not qdrant_url or not qdrant_api_key:
                raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set")

            logger.info(f"Connecting to Qdrant Cloud: {qdrant_url[:40]}...")
            self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
            logger.info("Qdrant Cloud client connected successfully")

            # Initialize Voyage AI embedding model
            logger.info(f"Loading Voyage AI embedding model: {embedding_model_id}...")
            self.embedding_model = get_embedding_model(embedding_model_id)
            self.embedding_dim = settings.RAG_TEXT_EMBEDDING_MODEL_DIM  # 1024 for voyage-law-2
            logger.info("Voyage AI embedding model loaded successfully")

            # Ensure collection exists
            self._ensure_collection()

            # Initialize reranker if enabled
            if self.use_reranker:
                try:
                    logger.info("Loading cross-encoder reranker...")
                    self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                    logger.info("Cross-encoder reranker initialized successfully")
                except Exception as e:
                    logger.warning(f"Could not initialize reranker: {e}. Proceeding without.")
                    self.use_reranker = False
                    self.reranker = None
            else:
                self.reranker = None

        except Exception as e:
            logger.error(f"Failed to initialize LegalQdrantRetriever: {e}")
            raise RuntimeError(f"Qdrant initialization failed: {e}") from e

    def _ensure_collection(self):
        """Create the collection if it doesn't exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            logger.info(f"Creating Qdrant collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Collection '{self.collection_name}' created")
        else:
            info = self.client.get_collection(self.collection_name)
            logger.info(f"Collection '{self.collection_name}' exists with {info.points_count} points")

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        """Add texts to the Qdrant collection."""
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(texts))]

        # Generate embeddings
        embeddings = self.embedding_model.embed_documents(texts)

        points = []
        for i, (text, embedding) in enumerate(zip(texts, embeddings)):
            payload = {"page_content": text}
            if metadatas and i < len(metadatas):
                payload.update(metadatas[i])

            points.append(
                PointStruct(
                    id=abs(hash(ids[i])) % (2**63),  # Qdrant needs int IDs
                    vector=embedding,
                    payload=payload,
                )
            )

        # Batch upsert
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(collection_name=self.collection_name, points=batch)

        logger.info(f"Added {len(points)} documents to Qdrant collection '{self.collection_name}'")

    def _vector_search(self, query: str, k: int) -> List[Document]:
        """Perform vector similarity search."""
        query_embedding = self.embedding_model.embed_query(query)

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=k,
        )

        documents = []
        for hit in results.points:
            payload = hit.payload or {}
            page_content = payload.pop("page_content", "")
            documents.append(
                Document(page_content=page_content, metadata={**payload, "score": hit.score})
            )

        if documents:
            top = documents[0].metadata
            logger.debug(
                f"Qdrant top hit | case_id={top.get('case_id', 'MISSING')} "
                f"paragraph_id={top.get('paragraph_id', 'MISSING')} score={top.get('score'):.3f}"
            )
        return documents

    def _rerank_results(self, query: str, documents: List[Document]) -> List[Document]:
        """Rerank documents using cross-encoder."""
        if not self.use_reranker or not self.reranker or not documents:
            return documents

        pairs = [(query, doc.page_content) for doc in documents]
        scores = self.reranker.predict(pairs)

        scored_docs = [(doc, float(score)) for doc, score in zip(documents, scores)]
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        return [doc for doc, _ in scored_docs]

    def _case_filtered_search(self, case_id: str, limit: int = 100) -> List[Document]:
        """Fetch ALL chunks for a specific case_id via Qdrant scroll filter.

        Used by case-aware retrieval: when the top vector hits cluster around
        a single court case, we pull the full judgment text so the reranker
        can select the best paragraphs spanning facts, reasoning, and holding.
        """
        logger.info(f"Case-aware fetch: scrolling all chunks for case_id={case_id!r} (limit={limit})")
        try:
            results, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="case_id", match=MatchValue(value=case_id))]
                ),
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as e:
            logger.warning(f"Case-filtered scroll failed for {case_id}: {e}")
            return []

        documents = []
        for hit in results:
            payload = dict(hit.payload or {})
            page_content = payload.pop("page_content", "")
            documents.append(
                Document(page_content=page_content, metadata={**payload, "score": 0.0})
            )

        logger.info(f"Case-aware fetch: got {len(documents)} chunks for {case_id}")
        return documents

    def retrieve(self, query: str) -> List[Document]:
        """Retrieve relevant documents for the given query.

        Two retrieval modes, selected by intent:

        * **Full-judgment mode** (when the query asks for a whole case — "X v Y",
          "summarize the case", "full judgment", "facts of the case", "holding in",
          etc.): triggered case-aware fetch lowered to 1 case_law hit in top 3.
          All chunks for the dominant case are returned in document order,
          bypassing the top-k reranker truncation entirely. This is the path
          that fixes "not explicitly stated in the retrieved text" for
          judgment-summary queries — the reranker was selecting query-similar
          header/disposition chunks and dropping body paragraphs.

        * **Narrow-question mode** (default — "what is Article 17?", "can a
          court override...?"): the reranker picks the top k chunks from the
          vector + case-aware merged pool, then we re-sort those k by document
          position before returning so the LLM sees narrative order.
        """
        full_judgment_intent = _detect_full_judgment_intent(query)
        logger.info(
            f"Performing Qdrant vector search for query: {query[:80]}... "
            f"(explicit_full_judgment_intent={full_judgment_intent})"
        )

        # Citation shortcut: if the query names a specific case_id (either as a
        # bracketed citation "[2022] GHACC 316" or canonical "GHACC_2022_316"),
        # fetch that case directly. Bare citations embed poorly — vector search
        # against the judgment body finds unrelated cases at low similarity.
        cited_case_id = _extract_case_id_from_query(query)
        if cited_case_id:
            logger.info(f"Citation shortcut: detected case_id={cited_case_id!r} in query")
            cited_chunks = self._case_filtered_search(cited_case_id, limit=500)
            if cited_chunks:
                ordered = _order_by_document_position(cited_chunks)
                logger.info(
                    f"Citation shortcut hit: returning {len(ordered)} chunks for "
                    f"{cited_case_id} in document order (bypassing vector search)"
                )
                return ordered
            logger.info(
                f"Citation shortcut miss: {cited_case_id} not in Qdrant; "
                f"falling back to vector search"
            )

        fetch_k = self.k * 4 if self.use_reranker else self.k
        results = self._vector_search(query, fetch_k)

        # (b) Implicit case-summary trigger — fires when keywords miss but the
        # embeddings + clustering strongly indicate the user is asking about
        # ONE specific case. Promotes the query to full-judgment mode below.
        implicit_case_id: Optional[str] = None
        if not full_judgment_intent and self.use_reranker:
            implicit_case_id = _detect_implicit_case_intent(query, results)
            if implicit_case_id:
                top_score = (results[0].metadata or {}).get("score")
                logger.info(
                    f"Implicit case-summary intent detected for "
                    f"case_id={implicit_case_id!r} "
                    f"(top_score={top_score!r}, no explicit keyword match)"
                )
                full_judgment_intent = True

        # --- Case-aware retrieval ---
        # Trigger threshold depends on intent. Full-judgment queries get a
        # looser trigger (1 case_law hit in top 3) since the user has already
        # told us they want a specific case. Narrow questions keep the stricter
        # 2-in-top-5 rule to avoid spuriously expanding into a full judgment
        # when the user only asked about a specific principle.
        if self.use_reranker and results:
            from collections import Counter

            if full_judgment_intent:
                top_n = results[:3]
                min_count = 1
            else:
                top_n = results[:5]
                min_count = 2

            case_counts = Counter()
            case_doc_types: dict[str, str] = {}
            for doc in top_n:
                cid = (doc.metadata or {}).get("case_id", "")
                dtype = (doc.metadata or {}).get("document_type", "")
                if cid:
                    case_counts[cid] += 1
                    case_doc_types[cid] = dtype

            dominant_case = None
            for cid, count in case_counts.most_common(1):
                if count >= min_count and case_doc_types.get(cid, "") == "case_law":
                    dominant_case = cid

            if dominant_case:
                logger.info(
                    f"Case-aware retrieval triggered for case_id={dominant_case!r} "
                    f"(mode={'full_judgment' if full_judgment_intent else 'default'}, "
                    f"appeared {case_counts[dominant_case]}x in top {len(top_n)})"
                )
                all_case_chunks = self._case_filtered_search(dominant_case, limit=500)

                if full_judgment_intent and all_case_chunks:
                    # Keep a small number of top vector hits from OTHER cases so
                    # queries like "how does Tuffuor relate to Article 144" still
                    # surface the cross-referenced statute/case alongside the
                    # full judgment text. Cap at 5 to avoid drowning the case
                    # in unrelated noise.
                    other_case_hits = [
                        d for d in results[:5]
                        if (d.metadata or {}).get("case_id", "") != dominant_case
                    ]
                    seen: set[tuple[str, str]] = set()
                    merged: list[Document] = []
                    for doc in all_case_chunks + other_case_hits:
                        key = (
                            (doc.metadata or {}).get("case_id", ""),
                            (doc.metadata or {}).get("paragraph_id", ""),
                        )
                        if key not in seen:
                            seen.add(key)
                            merged.append(doc)
                    ordered = _order_by_document_position(merged)
                    logger.info(
                        f"Full-judgment mode: returning {len(ordered)} chunks "
                        f"({len(all_case_chunks)} from {dominant_case} + "
                        f"{len(other_case_hits)} cross-reference) in document order "
                        f"(bypassing reranker truncation)"
                    )
                    return ordered

                if full_judgment_intent and not all_case_chunks:
                    logger.warning(
                        f"Full-judgment intent detected but no chunks fetched "
                        f"for {dominant_case}; falling back to default retrieval"
                    )

                seen: set[tuple[str, str]] = set()
                merged: list[Document] = []
                for doc in results + all_case_chunks:
                    key = (
                        (doc.metadata or {}).get("case_id", ""),
                        (doc.metadata or {}).get("paragraph_id", ""),
                    )
                    if key not in seen:
                        seen.add(key)
                        merged.append(doc)

                logger.info(
                    f"Merged pool: {len(merged)} unique docs "
                    f"(vector={len(results)}, case_scroll={len(all_case_chunks)})"
                )
                results = merged

        if self.use_reranker:
            results = self._rerank_results(query, results)
            results = results[: self.k]
            # Restore document order on the kept chunks so the LLM sees
            # facts → reasoning → holding, not rerank-score order.
            results = _order_by_document_position(results)
            logger.info(f"Applied reranking, returning top {len(results)} documents")

        return results



def get_qdrant_retriever(
    collection_name: str = "legal_docs",
    embedding_model_id: str = "voyage-law-2",
    k: int = 3,
    device: str = "cpu",
    use_reranker: bool = True,
) -> LegalQdrantRetriever:
    """Factory function to create a Qdrant retriever with singleton pattern."""
    global _qdrant_retriever_instance

    if _qdrant_retriever_instance is not None:
        logger.info("Returning existing LegalQdrantRetriever instance (singleton)")
        return _qdrant_retriever_instance

    logger.info(
        f"Creating new LegalQdrantRetriever | model: {embedding_model_id} | "
        f"collection: {collection_name} | k: {k} | device: {device} | reranker: {use_reranker}"
    )

    try:
        _qdrant_retriever_instance = LegalQdrantRetriever(
            collection_name=collection_name,
            embedding_model_id=embedding_model_id,
            k=k,
            device=device,
            use_reranker=use_reranker,
        )
        logger.info("LegalQdrantRetriever instance created and cached successfully")
        return _qdrant_retriever_instance
    except Exception as e:
        logger.error(f"Failed to create LegalQdrantRetriever: {e}")
        raise

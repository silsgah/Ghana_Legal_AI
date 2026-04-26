from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from loguru import logger

from ghana_legal.application.conversation_service.workflow.chains import (
    get_conversation_summary_chain,
    get_legal_expert_answer_chain,
    get_legal_expert_response_chain,
)
from ghana_legal.application.conversation_service.workflow.state import LegalExpertState
from ghana_legal.application.conversation_service.workflow.tools import (
    _retrieved_docs,
    _retrieved_sources,
    retriever,
)
from ghana_legal.application.conversation_service.workflow.validator import (
    build_repair_instruction,
    compute_confidence,
    strip_unbound_claims,
    validate,
)
from ghana_legal.config import settings
from ghana_legal.domain.legal_answer import LegalAnswer


async def retriever_node(state: LegalExpertState, config: RunnableConfig):
    """Custom retriever node — replaces the prebuilt ToolNode.

    The prebuilt ToolNode invokes the `@tool`-decorated function in a child
    context, which means contextvar.set() calls inside the tool do not
    propagate back to LangGraph state visible to downstream nodes. That broke
    the `state.retrieved` hoist in conversation_node — confidence dropped to
    insufficient on legitimate questions because the validator saw zero
    retrieved docs even when retrieval actually ran.

    This node calls the retriever directly, then writes both the ToolMessage
    (so the LLM sees the formatted sources in its message history) AND
    `state.retrieved` (so the validator can bind citations) explicitly.
    """
    messages = state.get("messages") or []
    if not messages:
        return {}
    last = messages[-1]
    tool_calls = getattr(last, "tool_calls", None) if isinstance(last, AIMessage) else None
    if not tool_calls:
        return {}

    tool_call = tool_calls[0]
    if tool_call.get("name") != "retrieve_legal_context":
        return {}

    query = (tool_call.get("args") or {}).get("query", "") or ""
    logger.info(f"retriever_node: query={query[:80]!r}")

    docs = retriever.retrieve(query)
    logger.info(f"retriever_node: returned {len(docs)} doc(s)")

    sources: list[dict] = []
    full_docs: list[dict] = []
    formatted_parts: list[str] = []

    for i, doc in enumerate(docs, 1):
        meta = doc.metadata or {}
        title = (
            meta.get("parties")
            or meta.get("filename", "").replace(".pdf", "").replace("_", " ")
        ).strip()
        court = meta.get("court", "")
        year = meta.get("year")
        sources.append({
            "title": title,
            "court": court,
            "year": str(year) if year is not None else "",
            "document_type": meta.get("document_type", ""),
            "case_id": meta.get("case_id", ""),
            "paragraph_id": meta.get("paragraph_id", ""),
        })
        full_docs.append({
            "case_id": meta.get("case_id", ""),
            "paragraph_id": meta.get("paragraph_id", ""),
            "paragraph_hash": meta.get("paragraph_hash", ""),
            "case_title": title,
            "court": court,
            "year": year,
            "document_type": meta.get("document_type", ""),
            "score": meta.get("score"),
            "page_content": doc.page_content,
        })
        header_parts = [str(p) for p in [title, court, year] if p]
        header = " | ".join(header_parts) if header_parts else f"Source {i}"
        content = meta.get("parent_content", doc.page_content)
        formatted_parts.append(f"[Source {i}: {header}]\n{content}")

    # Sources contextvar still feeds the post-graph SSE 'sources' event read by
    # generate_response.py. The docs contextvar is preserved as a fallback but
    # the canonical source for the validator is now state.retrieved below.
    _retrieved_sources.set(sources)
    _retrieved_docs.set(full_docs)

    tool_msg = ToolMessage(
        content="\n\n---\n\n".join(formatted_parts) if formatted_parts else "No relevant documents found.",
        tool_call_id=tool_call.get("id", ""),
        name="retrieve_legal_context",
    )

    return {
        "messages": [tool_msg],
        "retrieved": full_docs,
    }


async def conversation_node(state: LegalExpertState, config: RunnableConfig):
    """Router/answer dispatcher.

    First pass (no ToolMessage in history) → router chain (free-text + bind_tools).
    Second pass (last message is a ToolMessage from retrieval) → answer chain
    that emits a structured LegalAnswer envelope and writes it to state.
    """
    summary = state.get("summary", "")
    messages = state["messages"]
    is_post_retrieval = bool(messages) and isinstance(messages[-1], ToolMessage)

    chain_inputs = {
        "messages": messages,
        "legal_context": state.get("legal_context", ""),
        "expert_name": state["expert_name"],
        "expertise": state["expertise"],
        "style": state["style"],
        "summary": summary,
    }

    if not is_post_retrieval:
        # Router pass — unchanged from previous behavior.
        chain = get_legal_expert_response_chain()
        response = await chain.ainvoke(chain_inputs, config)
        return {"messages": response}

    # Answer pass — emit structured envelope. state.retrieved is already set
    # by the upstream retriever_node, so no contextvar plumbing here.
    retrieved = state.get("retrieved") or []
    chain = get_legal_expert_answer_chain()
    result = await chain.ainvoke(chain_inputs, config)

    if isinstance(result, LegalAnswer):
        envelope = result
    elif isinstance(result, dict):
        envelope = LegalAnswer(**result)
    else:
        # Local Ollama fallback returns an AIMessage — synthesize a minimal envelope
        # so downstream code always sees a LegalAnswer-shaped dict.
        logger.warning("Answer chain returned non-LegalAnswer; synthesizing envelope")
        envelope = LegalAnswer(
            human_text=getattr(result, "content", str(result)),
            retrieval_used=True,
        )

    envelope.retrieval_used = True
    # `retrieved` is already in state from retriever_node — no need to re-write it.
    return {
        "messages": AIMessage(content=envelope.human_text),
        "legal_answer": envelope.model_dump(),
    }


async def summarize_conversation_node(state: LegalExpertState):
    summary = state.get("summary", "")
    summary_chain = get_conversation_summary_chain(summary)

    response = await summary_chain.ainvoke(
        {
            "messages": state["messages"],
            "expert_name": state["expert_name"],
            "summary": summary,
        }
    )

    delete_messages = [
        RemoveMessage(id=m.id)
        for m in state["messages"][: -settings.TOTAL_MESSAGES_AFTER_SUMMARY]
    ]
    return {"summary": response.content, "messages": delete_messages}


async def summarize_context_node(state: LegalExpertState):
    context_summary_chain = get_context_summary_chain()

    response = await context_summary_chain.ainvoke(
        {
            "context": state["messages"][-1].content,
        }
    )
    state["messages"][-1].content = response.content

    return {}


async def validate_answer_node(state: LegalExpertState, config: RunnableConfig):
    """Run the citation validator on the answer-pass envelope, with one-shot repair.

    Flow:
      1. Read envelope from state.
      2. validate() → if pass, compute confidence and return.
      3. On fail, build a corrective HumanMessage listing the violations and the
         retrieved sources, append it to messages, re-invoke the answer chain
         to produce a corrected envelope.
      4. validate() again. If still failing, strip unbound claims (downgrade)
         and let compute_confidence assign the resulting tier.

    Skips entirely if no envelope exists (no-retrieval branch — connector_node
    will backfill a synthetic envelope after this).
    """
    envelope_dict = state.get("legal_answer")
    if not envelope_dict:
        return {}

    retrieved = state.get("retrieved") or []
    envelope = LegalAnswer(**envelope_dict)
    result = validate(envelope, retrieved)

    if not result.passed:
        logger.warning(
            f"Answer validation failed ({len(result.violations)} violations); attempting one-shot repair"
        )
        repair_msg = HumanMessage(content=build_repair_instruction(result.violations, retrieved))

        chain = get_legal_expert_answer_chain()
        try:
            repaired = await chain.ainvoke(
                {
                    "messages": list(state["messages"]) + [repair_msg],
                    "legal_context": state.get("legal_context", ""),
                    "expert_name": state["expert_name"],
                    "expertise": state["expertise"],
                    "style": state["style"],
                    "summary": state.get("summary", ""),
                },
                config,
            )
        except Exception as repair_error:
            logger.error(f"Repair invocation failed: {repair_error}; downgrading instead")
            repaired = None

        if isinstance(repaired, LegalAnswer):
            envelope = repaired
        elif isinstance(repaired, dict):
            envelope = LegalAnswer(**repaired)
        envelope.retrieval_used = True

        result = validate(envelope, retrieved)

        if not result.passed:
            logger.warning(
                f"Repair failed ({len(result.violations)} violations remain); stripping unbound claims"
            )
            pre_strip_count = len(envelope.claims)
            envelope = strip_unbound_claims(envelope, result)
            # Re-validate the stripped envelope so confidence reflects what's left.
            result = validate(envelope, retrieved)
            # If stripping took the count to zero, the model invented every
            # citation it tried — refuse the answer rather than show stripped
            # prose with a warning. Distinct from "model emitted 0 claims to
            # begin with", which is just a structural-output generation issue.
            if pre_strip_count > 0 and len(envelope.claims) == 0:
                envelope.confidence = "insufficient"
                logger.warning(
                    f"All {pre_strip_count} claims stripped (every citation invented); refusing"
                )
                return {
                    "legal_answer": envelope.model_dump(),
                    "repair_attempts": state.get("repair_attempts", 0) + 1,
                }

    envelope.confidence = compute_confidence(result, envelope)
    n_claims = len(envelope.claims)
    n_retrieved = len(retrieved)
    logger.info(
        f"Answer validated: confidence={envelope.confidence} "
        f"claims={n_claims} retrieved={n_retrieved} "
        f"bound_ratio={result.bound_ratio:.2f} distinct_cases={result.distinct_cases} "
        f"min_similarity={result.min_similarity:.3f}"
    )
    # When confidence drops to low/insufficient, dump the envelope shape so we
    # can triage without rerunning the query. Avoids logging full content.
    if envelope.confidence in ("low", "insufficient"):
        retrieved_keys = [(d.get("case_id"), d.get("paragraph_id")) for d in retrieved[:5]]
        cited_keys = [
            (c.case_id, c.paragraph_id)
            for cl in envelope.claims for c in cl.citations
        ]
        logger.warning(
            f"Low/insufficient diagnostics — "
            f"retrieved_keys={retrieved_keys} cited_keys={cited_keys} "
            f"violations={[(v.kind, v.claim_index) for v in result.violations]}"
        )

    # Don't write to messages here — the original AIMessage from conversation_node
    # is already in history. The user sees the (possibly repaired) text via the
    # envelope's human_text in the SSE stream, not via the message history.
    return {
        "legal_answer": envelope.model_dump(),
        "repair_attempts": (state.get("repair_attempts", 0) + 1) if not result.passed else 0,
    }


async def connector_node(state: LegalExpertState):
    """Backfill a synthetic envelope when the router answered without retrieval.

    Ensures downstream consumers (SSE emitter, validator, UI renderer) always
    see a `legal_answer` dict in state regardless of which branch the graph took.
    """
    if state.get("legal_answer"):
        return {}

    last = state["messages"][-1] if state.get("messages") else None
    text = getattr(last, "content", "") if last else ""
    if not isinstance(text, str):
        text = str(text)
    envelope = LegalAnswer(human_text=text, retrieval_used=False)
    # No retrieval happened, so confidence is undefined — leave at the model's
    # default. The API layer treats missing confidence as "not insufficient".
    return {"legal_answer": envelope.model_dump()}
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode
from loguru import logger

from ghana_legal.application.conversation_service.workflow.chains import (
    get_conversation_summary_chain,
    get_legal_expert_answer_chain,
    get_legal_expert_response_chain,
)
from ghana_legal.application.conversation_service.workflow.state import LegalExpertState
from ghana_legal.application.conversation_service.workflow.tools import (
    get_retrieved_docs,
    tools,
)
from ghana_legal.application.conversation_service.workflow.validator import (
    build_repair_instruction,
    compute_confidence,
    strip_unbound_claims,
    validate,
)
from ghana_legal.config import settings
from ghana_legal.domain.legal_answer import LegalAnswer

retriever_node = ToolNode(tools)


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

    # Answer pass — hoist retrieved docs into state and emit structured envelope.
    retrieved = get_retrieved_docs()
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
    return {
        "messages": AIMessage(content=envelope.human_text),
        "retrieved": retrieved,
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
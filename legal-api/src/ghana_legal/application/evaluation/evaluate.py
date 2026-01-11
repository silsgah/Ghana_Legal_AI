import asyncio

import opik
from loguru import logger
from opik.evaluation import evaluate
from opik.evaluation.metrics import (
    AnswerRelevance,
    ContextPrecision,
    ContextRecall,
    Hallucination,
    Moderation,
)

from ghana_legal.application.conversation_service.generate_response import get_response
from ghana_legal.application.conversation_service.workflow.state import state_to_str
from ghana_legal.config import settings
from ghana_legal.domain.legal_expert_factory import LegalExpertFactory


async def evaluation_task(x: dict) -> dict:
    """Calls agentic app logic to evaluate legal expert responses.

    Args:
        x: Dictionary containing evaluation data with the following keys:
            messages: List of conversation messages where all but the last are inputs
                and the last is the expected output
            expert_id: ID of the legal expert to use

    Returns:
        dict: Dictionary with evaluation results containing:
            input: Original input messages
            context: Context used for generating the response
            output: Generated response from expert
            expected_output: Expected answer for comparison
    """

    expert_factory = LegalExpertFactory()
    expert = expert_factory.get_legal_expert(x["expert_id"])

    input_messages = x["messages"][:-1]
    expected_output_message = x["messages"][-1]

    response, latest_state = await get_response(
        messages=input_messages,
        expert_id=expert.id,
        expert_name=expert.name,
        expertise=expert.expertise,
        style=expert.style,
        legal_context="",
        new_thread=True,
    )
    context = state_to_str(latest_state)

    return {
        "input": input_messages,
        "context": context,
        "output": response,
        "expected_output": expected_output_message,
    }


def get_used_prompts() -> list[opik.Prompt]:
    client = opik.Opik()

    prompts = [
        client.get_prompt(name="legal_expert_character_card"),
        client.get_prompt(name="summary_prompt"),
        client.get_prompt(name="extend_summary_prompt"),
    ]
    prompts = [p for p in prompts if p is not None]

    return prompts


def evaluate_agent(
    dataset: opik.Dataset | None,
    workers: int = 2,
    nb_samples: int | None = None,
) -> None:
    """Evaluates an agent using specified metrics and dataset.

    Runs evaluation using Opik framework with configured metrics for hallucination,
    answer relevance, moderation, and context recall.

    Args:
        dataset: Dataset containing evaluation examples.
            Must contain messages and philosopher_id.
        workers: Number of parallel workers to use for evaluation.
            Defaults to 2.
        nb_samples: Optional number of samples to evaluate.
            If None, evaluates the entire dataset.

    Raises:
        ValueError: If dataset is None
        AssertionError: If COMET_API_KEY is not set

    Returns:
        None
    """

    assert settings.COMET_API_KEY, (
        "COMET_API_KEY is not set. We need it to track the experiment with Opik."
    )

    if not dataset:
        raise ValueError("Dataset is 'None'.")

    logger.info("Starting evaluation...")

    experiment_config = {
        "model_id": settings.GROQ_LLM_MODEL,
        "dataset_name": dataset.name,
    }
    used_prompts = get_used_prompts()

    scoring_metrics = [
        Hallucination(),
        AnswerRelevance(),
        Moderation(),
        ContextRecall(),
        ContextPrecision(),
    ]

    logger.info("Evaluation details:")
    logger.info(f"Dataset: {dataset.name}")
    logger.info(f"Metrics: {[m.__class__.__name__ for m in scoring_metrics]}")

    evaluate(
        dataset=dataset,
        task=lambda x: asyncio.run(evaluation_task(x)),
        scoring_metrics=scoring_metrics,
        experiment_config=experiment_config,
        task_threads=workers,
        nb_samples=nb_samples,
        prompts=used_prompts,
    )

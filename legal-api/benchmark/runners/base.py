"""
Base Model Runner
=================

Abstract base class for all model runners. Each runner wraps a specific
LLM backend (Groq, OpenAI, Ollama) and provides a uniform interface for
generating answers given a question and optional retrieval context.
"""

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of a single model generation."""
    answer: str
    model_name: str
    latency_seconds: float
    token_count: Optional[int] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class ModelRunner(ABC):
    """
    Abstract base class for model runners.

    Each runner must implement:
    - name: Human-readable name for reports
    - generate(): Produce an answer for a given question
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this runner configuration."""
        ...

    @abstractmethod
    async def generate(
        self,
        question: str,
        context: list[str] | None = None,
        system_prompt: str | None = None,
    ) -> GenerationResult:
        """
        Generate an answer for a legal question.

        Args:
            question: The legal question to answer.
            context: Optional retrieved context passages (for RAG mode).
            system_prompt: Optional system prompt override.

        Returns:
            GenerationResult with the answer, latency, and metadata.
        """
        ...

    def _build_prompt(
        self,
        question: str,
        context: list[str] | None = None,
        system_prompt: str | None = None,
    ) -> tuple[str, str]:
        """
        Build system and user prompts for generation.

        Returns:
            Tuple of (system_message, user_message).
        """
        if system_prompt is None:
            system_prompt = (
                "You are a legal expert specializing in Ghana's 1992 Constitution "
                "and Ghanaian case law. Provide accurate, well-cited answers "
                "grounded in the legal text. If you are unsure, acknowledge "
                "the uncertainty. Always cite specific articles, sections, or "
                "case names when applicable."
            )

        if context:
            context_block = "\n\n".join(
                f"[Document {i+1}]: {c}" for i, c in enumerate(context)
            )
            user_message = (
                f"Based on the following legal context, answer the question.\n\n"
                f"--- CONTEXT ---\n{context_block}\n--- END CONTEXT ---\n\n"
                f"Question: {question}"
            )
        else:
            user_message = f"Question: {question}"

        return system_prompt, user_message

    async def generate_timed(
        self,
        question: str,
        context: list[str] | None = None,
        system_prompt: str | None = None,
    ) -> GenerationResult:
        """Generate with timing wrapper."""
        start = time.perf_counter()
        try:
            result = await self.generate(question, context, system_prompt)
            result.latency_seconds = time.perf_counter() - start
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.error(f"[{self.name}] Generation failed: {e}")
            return GenerationResult(
                answer="",
                model_name=self.name,
                latency_seconds=elapsed,
                error=str(e),
            )

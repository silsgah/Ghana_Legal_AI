"""
Groq Runner
===========

Runs Llama-3-70B and other models via the Groq inference API.
Supports both zero-shot (no context) and RAG (with context) modes.
"""

import os
import logging

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from benchmark.runners.base import ModelRunner, GenerationResult

logger = logging.getLogger(__name__)


class GroqRunner(ModelRunner):
    """Model runner using the Groq API."""

    def __init__(
        self,
        model: str = "llama-3.3-70b-versatile",
        api_key: str | None = None,
        temperature: float = 0.1,
        label: str | None = None,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.temperature = temperature
        self._label = label
        self.llm = ChatGroq(
            model=self.model,
            api_key=self.api_key,
            temperature=self.temperature,
        )

    @property
    def name(self) -> str:
        return self._label or f"Groq ({self.model})"

    async def generate(
        self,
        question: str,
        context: list[str] | None = None,
        system_prompt: str | None = None,
    ) -> GenerationResult:
        sys_msg, user_msg = self._build_prompt(question, context, system_prompt)

        messages = [
            SystemMessage(content=sys_msg),
            HumanMessage(content=user_msg),
        ]

        response = await self.llm.ainvoke(messages)

        return GenerationResult(
            answer=response.content,
            model_name=self.name,
            latency_seconds=0.0,  # filled by generate_timed
            metadata={
                "model": self.model,
                "has_context": context is not None,
                "context_count": len(context) if context else 0,
            },
        )

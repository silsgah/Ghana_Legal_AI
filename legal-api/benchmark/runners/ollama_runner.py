"""
Ollama Runner
=============

Runs the fine-tuned ghana-legal model (or any Ollama-hosted model)
via the local Ollama API. Supports both zero-shot and RAG modes.
"""

import os
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from benchmark.runners.base import ModelRunner, GenerationResult

logger = logging.getLogger(__name__)


class OllamaRunner(ModelRunner):
    """Model runner using a local Ollama instance."""

    def __init__(
        self,
        model: str = "ghana-legal",
        base_url: str | None = None,
        temperature: float = 0.1,
        label: str | None = None,
    ):
        self.model = model
        self.base_url = base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.temperature = temperature
        self._label = label

        # Lazy import to avoid requiring ollama if not used
        from langchain_ollama import ChatOllama
        self.llm = ChatOllama(
            model=self.model,
            base_url=self.base_url,
            temperature=self.temperature,
        )

    @property
    def name(self) -> str:
        return self._label or f"Ollama ({self.model})"

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
            latency_seconds=0.0,
            metadata={
                "model": self.model,
                "has_context": context is not None,
                "context_count": len(context) if context else 0,
            },
        )

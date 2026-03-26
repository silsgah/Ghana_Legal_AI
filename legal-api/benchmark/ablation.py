"""
Ablation Study Runner
=====================

Runs the system with components progressively enabled to measure
the contribution of each component to overall performance.

Ablation configurations:
1. Base model only (no RAG, no fine-tuning)
2. + RAG with retrieval context
3. + Fine-tuned model (SFT)
4. + Fine-tuned model (SFT + DPO)

Each configuration is run as a separate runner, allowing the harness
to compare scores across configurations.
"""

import asyncio
import logging
from dataclasses import dataclass

from benchmark.harness import EvaluationHarness, BenchmarkResults
from benchmark.runners.base import ModelRunner
from benchmark.report import save_report, generate_markdown_table

logger = logging.getLogger(__name__)


@dataclass
class AblationConfig:
    """Configuration for a single ablation run."""
    name: str
    runner: ModelRunner
    use_context: bool
    description: str


def build_ablation_configs() -> list[AblationConfig]:
    """
    Build the standard ablation configurations.

    Returns:
        List of AblationConfig objects, one per ablation step.
    """
    configs = []

    # 1. Base Llama-3-70B (zero-shot, no RAG)
    from benchmark.runners.groq_runner import GroqRunner
    configs.append(AblationConfig(
        name="Base (Llama-3-70B, no RAG)",
        runner=GroqRunner(
            model="llama-3.3-70b-versatile",
            label="Base (Llama-3-70B, no RAG)",
        ),
        use_context=False,
        description="Teacher model with no retrieval, no fine-tuning",
    ))

    # 2. Llama-3-70B + RAG context
    configs.append(AblationConfig(
        name="+ RAG Context",
        runner=GroqRunner(
            model="llama-3.3-70b-versatile",
            label="Llama-3-70B + RAG",
        ),
        use_context=True,
        description="Teacher model with retrieval context from benchmark",
    ))

    # 3. Llama-3-8B (smaller model baseline, no RAG)
    configs.append(AblationConfig(
        name="Llama-3-8B (no RAG)",
        runner=GroqRunner(
            model="llama-3.1-8b-instant",
            label="Llama-3-8B (no RAG)",
        ),
        use_context=False,
        description="Smaller model without retrieval — lower bound",
    ))

    # 4. Llama-3-8B + RAG
    configs.append(AblationConfig(
        name="Llama-3-8B + RAG",
        runner=GroqRunner(
            model="llama-3.1-8b-instant",
            label="Llama-3-8B + RAG",
        ),
        use_context=True,
        description="Smaller model with retrieval context",
    ))

    # 5. Fine-tuned model (zero-shot) — requires Ollama
    try:
        from benchmark.runners.ollama_runner import OllamaRunner
        configs.append(AblationConfig(
            name="Fine-tuned LFM2 (no RAG)",
            runner=OllamaRunner(
                model="ghana-legal",
                label="Fine-tuned LFM2 (no RAG)",
            ),
            use_context=False,
            description="Fine-tuned model without retrieval context",
        ))

        # 6. Fine-tuned model + RAG
        configs.append(AblationConfig(
            name="Fine-tuned LFM2 + RAG",
            runner=OllamaRunner(
                model="ghana-legal",
                label="Fine-tuned LFM2 + RAG",
            ),
            use_context=True,
            description="Fine-tuned model with retrieval context — full system",
        ))
    except Exception:
        logger.warning(
            "Ollama runner not available — skipping fine-tuned model ablations. "
            "Install langchain-ollama and ensure Ollama is running."
        )

    return configs


async def run_ablation(
    configs: list[AblationConfig] | None = None,
    dataset_path: str | None = None,
    output_dir: str = "benchmark/results/ablation",
    max_concurrent: int = 3,
) -> BenchmarkResults:
    """
    Run the ablation study.

    Args:
        configs: Ablation configurations (defaults to standard configs).
        dataset_path: Path to dataset JSON.
        output_dir: Directory to save results.
        max_concurrent: Maximum concurrent API calls.

    Returns:
        BenchmarkResults with all ablation run results.
    """
    configs = configs or build_ablation_configs()

    harness = EvaluationHarness(
        dataset_path=dataset_path,
        max_concurrent=max_concurrent,
    )

    all_results = BenchmarkResults(
        dataset_version=harness.dataset.version,
        dataset_size=harness.dataset.total,
    )

    for i, config in enumerate(configs, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Ablation {i}/{len(configs)}: {config.name}")
        logger.info(f"Description: {config.description}")
        logger.info(f"Use context: {config.use_context}")
        logger.info(f"{'='*60}")

        try:
            result = await harness.run_runner(
                runner=config.runner,
                use_context=config.use_context,
            )
            all_results.runner_results.append(result)
        except Exception as e:
            logger.error(f"Ablation '{config.name}' failed: {e}")

    # Save reports
    saved = save_report(all_results, output_dir)

    print("\n" + "=" * 60)
    print("ABLATION STUDY COMPLETE")
    print("=" * 60)
    print(f"\n{generate_markdown_table(all_results)}\n")
    print(f"Reports saved to: {output_dir}")

    return all_results


if __name__ == "__main__":
    asyncio.run(run_ablation())

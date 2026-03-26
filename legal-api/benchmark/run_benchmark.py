"""
CLI Entry Point for LegalBench-GH Benchmark
============================================

Usage:
    # Run all baselines (requires GROQ_API_KEY, OPENAI_API_KEY)
    python -m benchmark.run_benchmark --mode baselines

    # Run a single model
    python -m benchmark.run_benchmark --runner groq --model llama-3.3-70b-versatile

    # Run without RAG context (zero-shot)
    python -m benchmark.run_benchmark --runner groq --model llama-3.3-70b-versatile --no-context

    # Run with local Ollama model
    python -m benchmark.run_benchmark --runner ollama --model ghana-legal

    # Run a quick smoke test (3 questions only)
    python -m benchmark.run_benchmark --mode smoke-test

    # Generate report from previous results
    python -m benchmark.run_benchmark --report latex --results-file benchmark/results/results.json

    # Validate the dataset schema
    python -m benchmark.run_benchmark --validate-dataset
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure the legal-api/src is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from benchmark.dataset.schema import load_dataset
from benchmark.harness import EvaluationHarness
from benchmark.report import save_report, generate_markdown_table, generate_latex_table

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("benchmark")


def build_runners(args) -> list:
    """Build model runners based on CLI args."""
    runners = []

    if args.mode == "baselines" or args.runner == "groq":
        from benchmark.runners.groq_runner import GroqRunner

        if args.mode == "baselines":
            # Add both Llama models
            runners.append(GroqRunner(
                model="llama-3.3-70b-versatile",
                label="Llama-3-70B (zero-shot)",
            ))
            runners.append(GroqRunner(
                model="llama-3.1-8b-instant",
                label="Llama-3-8B (zero-shot)",
            ))
        else:
            model = args.model or "llama-3.3-70b-versatile"
            runners.append(GroqRunner(model=model))

    if args.mode == "baselines" or args.runner == "openai":
        from benchmark.runners.openai_runner import OpenAIRunner

        if args.mode == "baselines":
            runners.append(OpenAIRunner(
                model="gpt-4o",
                label="GPT-4o (zero-shot)",
            ))
        else:
            model = args.model or "gpt-4o"
            runners.append(OpenAIRunner(model=model))

    if args.runner == "ollama":
        from benchmark.runners.ollama_runner import OllamaRunner
        model = args.model or "ghana-legal"
        runners.append(OllamaRunner(model=model))

    return runners


async def run_smoke_test():
    """Quick smoke test with 3 questions to verify connectivity."""
    logger.info("=== SMOKE TEST (3 questions) ===")

    dataset = load_dataset()
    questions = dataset.questions[:3]

    from benchmark.runners.groq_runner import GroqRunner
    runner = GroqRunner(
        model="llama-3.3-70b-versatile",
        label="Smoke Test (Groq)",
    )

    harness = EvaluationHarness(max_concurrent=1)
    result = await harness.run_runner(runner, questions=questions)

    print("\n=== SMOKE TEST RESULTS ===")
    for qr in result.question_results:
        status = "✅" if not qr.error else f"❌ {qr.error}"
        print(f"  [{qr.question_id}] {status}")
        if qr.scores:
            for metric, score in sorted(qr.scores.items()):
                passed = "✅" if qr.passed.get(metric, False) else "❌"
                print(f"    {passed} {metric}: {score:.3f}")
        print(f"    ⏱️  Latency: {qr.latency_seconds:.2f}s")
    print()

    print(f"Average scores: {result.avg_scores}")
    print(f"Average latency: {result.avg_latency:.2f}s")


async def run_benchmark(args):
    """Run the full benchmark."""
    runners = build_runners(args)
    if not runners:
        logger.error("No runners configured. Use --runner or --mode baselines.")
        sys.exit(1)

    use_context = not args.no_context
    harness = EvaluationHarness(
        dataset_path=args.dataset,
        max_concurrent=args.concurrency,
    )

    # Run baselines with context if in baseline mode
    if args.mode == "baselines":
        # First run: zero-shot (no context)
        logger.info("--- Phase 1: Zero-shot (no context) ---")
        results_zeroshot = await harness.run(runners, use_context=False)

        # Second run: with context (RAG)
        rag_runners = []
        from benchmark.runners.groq_runner import GroqRunner
        from benchmark.runners.openai_runner import OpenAIRunner

        rag_runners.append(GroqRunner(
            model="llama-3.3-70b-versatile", label="Llama-3-70B + RAG"
        ))
        rag_runners.append(OpenAIRunner(model="gpt-4o", label="GPT-4o + RAG"))

        logger.info("--- Phase 2: With RAG context ---")
        results_rag = await harness.run(rag_runners, use_context=True)

        # Merge results
        results_zeroshot.runner_results.extend(results_rag.runner_results)
        results = results_zeroshot
    else:
        results = await harness.run(runners, use_context=use_context)

    # Save reports
    output_dir = Path(args.output_dir)
    saved = save_report(results, output_dir)

    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)
    print(f"\n{generate_markdown_table(results)}\n")
    print(f"Reports saved to: {output_dir}")
    for fmt, path in saved.items():
        print(f"  {fmt}: {path}")


def validate_dataset(args):
    """Validate the dataset schema."""
    try:
        dataset = load_dataset(args.dataset)
        summary = dataset.summary()
        print("✅ Dataset is valid!")
        print(f"   Total questions: {summary['total']}")
        print(f"   By category: {json.dumps(summary['by_category'], indent=4)}")
        print(f"   By difficulty: {json.dumps(summary['by_difficulty'], indent=4)}")
    except Exception as e:
        print(f"❌ Dataset validation failed: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="LegalBench-GH Evaluation Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Mode
    parser.add_argument(
        "--mode",
        choices=["baselines", "smoke-test", "single"],
        default="single",
        help="Benchmark mode: 'baselines' runs all models, 'smoke-test' runs 3 questions",
    )

    # Runner config
    parser.add_argument(
        "--runner",
        choices=["groq", "openai", "ollama"],
        help="Model runner backend",
    )
    parser.add_argument(
        "--model",
        help="Model name/ID for the selected runner",
    )
    parser.add_argument(
        "--no-context",
        action="store_true",
        help="Run without retrieval context (zero-shot mode)",
    )

    # Dataset
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Path to dataset JSON (default: benchmark/dataset/legalbench_gh.json)",
    )

    # Output
    parser.add_argument(
        "--output-dir",
        default="benchmark/results",
        help="Directory to save results (default: benchmark/results)",
    )

    # Concurrency
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Maximum concurrent API calls (default: 3)",
    )

    # Utilities
    parser.add_argument(
        "--validate-dataset",
        action="store_true",
        help="Validate the dataset schema and exit",
    )
    parser.add_argument(
        "--report",
        nargs="+",
        help="Generate report from existing results (e.g. latex markdown)",
    )
    parser.add_argument(
        "--results-file",
        type=Path,
        help="Path to results JSON file for report generation",
    )

    args = parser.parse_args()

    if args.validate_dataset:
        validate_dataset(args)
        return

    if args.report:
        if not args.results_file or not args.results_file.exists():
            print("❌ --results-file required and must exist for report generation")
            sys.exit(1)
        
        with open(args.results_file) as f:
            data = json.load(f)
        
        # reconstruct BenchmarkResults (basic)
        from benchmark.harness import BenchmarkResults, RunnerResult, QuestionResult
        results = BenchmarkResults(
            dataset_version=data.get("dataset_version", ""),
            dataset_size=data.get("dataset_size", 0),
            timestamp=data.get("timestamp", ""),
        )
        
        # We need to reconstruct runner results to use the report generator
        # This is a bit hacky as we don't have full QuestionResult objects in JSON usually unless we saved them
        # creating dummy runner results with avg_scores is enough for table generation
        for r_data in data.get("runners", []):
            rr = RunnerResult(
                runner_name=r_data["name"],
                question_results=[] # We don't have per-question detail in summary JSON unless we saved it
            )
            # Re-inject avg_scores into the object (mocking the property)
            # Since avg_scores is a property, we can't set it. 
            # We need to modify RunnerResult or subclass it, or validly populate question_results.
            # OR we can just modify report.py to accept dicts? 
            # OR we can make avg_scores a field in RunnerResult dataclass if we change it.
            # But wait, RunnerResult avg_scores IS a property.
            
            # Alternative: Monkey patch or just creating a mock object
            class MockRunnerResult:
                def __init__(self, name, scores, latency):
                    self.runner_name = name
                    self.avg_scores = scores
                    self.avg_latency = latency
                    self.question_results = [] # empty
                
                def by_category(self, cat): return {} # not supported in summary-only reconstruction

            mock_rr = MockRunnerResult(
                r_data["name"], 
                r_data["avg_scores"], 
                r_data.get("avg_latency", 0.0)
            )
            results.runner_results.append(mock_rr)

        saved = save_report(results, args.output_dir, formats=args.report)
        print(f"Reports saved to: {args.output_dir}")
        for fmt, path in saved.items():
            print(f"  {fmt}: {path}")
        return

    if args.mode == "smoke-test":
        asyncio.run(run_smoke_test())
    else:
        asyncio.run(run_benchmark(args))


if __name__ == "__main__":
    main()

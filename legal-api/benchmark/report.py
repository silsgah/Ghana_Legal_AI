"""
Results Reporter
================

Generates formatted output from benchmark results:
- Markdown tables (for README / walkthrough)
- LaTeX tables (drop-in for paper/main.tex)
- JSON (machine-readable)
"""

import json
from pathlib import Path

from benchmark.harness import BenchmarkResults, RunnerResult


# Metric display names and ordering
# Keys must match the class names returned by DeepEval (e.g. AnswerRelevancyMetric)
METRIC_DISPLAY = {
    "AnswerRelevancyMetric": "Ans. Rel.",
    "FaithfulnessMetric": "Faith.",
    "ContextualPrecisionMetric": "Ctx. Prec.",
    "ContextualRecallMetric": "Ctx. Rec.",
    "Legal Accuracy": "Legal Acc.",
    "Legal Relevance": "Legal Rel.",
    "Legal Authority": "Legal Auth.",
}

METRIC_ORDER = list(METRIC_DISPLAY.keys())


def generate_markdown_table(results: BenchmarkResults) -> str:
    """
    Generate a markdown comparison table from benchmark results.
    """
    if not results.runner_results:
        return "No results to display."

    # Gather all metrics across all runners
    all_metrics = set()
    for rr in results.runner_results:
        all_metrics.update(rr.avg_scores.keys())

    # Use ordered metrics
    ordered_metrics = [m for m in METRIC_ORDER if m in all_metrics]

    # Header
    header_cols = ["System"] + [METRIC_DISPLAY.get(m, m) for m in ordered_metrics] + ["Latency"]
    header = "| " + " | ".join(header_cols) + " |"
    separator = "| " + " | ".join(["---"] * len(header_cols)) + " |"

    # Rows
    rows = []
    for rr in results.runner_results:
        cols = [rr.runner_name]
        for metric in ordered_metrics:
            score = rr.avg_scores.get(metric, 0.0)
            cols.append(f"{score:.2f}")
        cols.append(f"{rr.avg_latency:.1f}s")
        rows.append("| " + " | ".join(cols) + " |")

    return "\n".join([header, separator] + rows)


def generate_latex_table(results: BenchmarkResults, bold_best: bool = True) -> str:
    """
    Generate a LaTeX table ready for drop-in to the ACL paper.
    """
    if not results.runner_results:
        return "% No results to display."

    all_metrics = set()
    for rr in results.runner_results:
        all_metrics.update(rr.avg_scores.keys())
    
    ordered_metrics = [m for m in METRIC_ORDER if m in all_metrics]
    short_names = [METRIC_DISPLAY.get(m, m) for m in ordered_metrics]

    # Find best score per metric for bolding
    best_scores = {}
    if bold_best:
        for metric in ordered_metrics:
            scores = [rr.avg_scores.get(metric, 0.0) for rr in results.runner_results]
            best_scores[metric] = max(scores) if scores else 0.0

    # Build LaTeX
    n_cols = len(ordered_metrics)
    col_spec = "l" + "c" * n_cols
    header_row = " & ".join(
        [r"\textbf{System}"] + [rf"\textbf{{{s}}}" for s in short_names]
    )

    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\small",
        rf"\begin{{tabular}}{{{col_spec}}}",
        r"\toprule",
        header_row + r" \\",
        r"\midrule",
    ]

    for rr in results.runner_results:
        cols = [rr.runner_name.replace("_", r"\_")]
        for metric in ordered_metrics:
            score = rr.avg_scores.get(metric, 0.0)
            formatted = f"{score:.2f}"
            if bold_best and abs(score - best_scores.get(metric, -1)) < 0.001:
                formatted = rf"\textbf{{{formatted}}}"
            cols.append(formatted)
        lines.append(" & ".join(cols) + r" \\")

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\caption{LegalBench-GH benchmark results. Best results per metric in \textbf{bold}.}",
        r"\label{tab:benchmark-results}",
        r"\end{table*}",
    ])

    return "\n".join(lines)


def generate_category_breakdown(
    runner_result: RunnerResult,
) -> str:
    """
    Generate a markdown table showing scores broken down by question category.
    """
    from benchmark.dataset.schema import QuestionCategory

    categories = [c.value for c in QuestionCategory]
    all_metrics = set()
    for qr in runner_result.question_results:
        all_metrics.update(qr.scores.keys())
    ordered_metrics = [m for m in METRIC_ORDER if m in all_metrics]

    header_cols = ["Category"] + [METRIC_DISPLAY.get(m, m) for m in ordered_metrics] + ["Count"]
    header = "| " + " | ".join(header_cols) + " |"
    separator = "| " + " | ".join(["---"] * len(header_cols)) + " |"

    rows = []
    for cat in categories:
        cat_scores = runner_result.by_category(cat)
        if not cat_scores:
            continue
        count = len([qr for qr in runner_result.question_results if qr.category == cat])
        cols = [cat.replace("_", " ").title()]
        for metric in ordered_metrics:
            score = cat_scores.get(metric, 0.0)
            cols.append(f"{score:.2f}")
        cols.append(str(count))
        rows.append("| " + " | ".join(cols) + " |")

    return "\n".join([header, separator] + rows)


def save_report(
    results: BenchmarkResults,
    output_dir: str | Path = "benchmark/results",
    formats: list[str] | None = None,
) -> dict[str, Path]:
    """
    Save benchmark results in multiple formats.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    formats = formats or ["markdown", "latex", "json"]

    saved = {}

    if "json" in formats:
        json_path = output_dir / "results.json"
        results.save(json_path)
        saved["json"] = json_path

    if "markdown" in formats:
        md_path = output_dir / "results.md"
        content = [
            "# LegalBench-GH Benchmark Results\n",
            f"**Dataset**: v{results.dataset_version} ({results.dataset_size} questions)\n",
            f"**Timestamp**: {results.timestamp}\n",
            "\n## Main Results\n",
            generate_markdown_table(results),
            "",
        ]
        # Add per-runner category breakdowns
        for rr in results.runner_results:
            content.extend([
                f"\n### {rr.runner_name} — Category Breakdown\n",
                generate_category_breakdown(rr),
                "",
            ])

        with open(md_path, "w") as f:
            f.write("\n".join(content))
        saved["markdown"] = md_path

    if "latex" in formats:
        tex_path = output_dir / "results_table.tex"
        with open(tex_path, "w") as f:
            f.write(generate_latex_table(results))
        saved["latex"] = tex_path

    return saved

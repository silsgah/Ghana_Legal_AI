"""
LegalBench-GH: Evaluation Benchmark Framework for Ghana Legal AI
================================================================

A modular benchmark for evaluating legal QA systems on Ghanaian law.
Supports multiple model backends, 7-metric scoring, baseline comparisons,
ablation studies, and LaTeX/Markdown report generation.

Usage:
    python -m benchmark.run_benchmark --mode baselines
    python -m benchmark.run_benchmark --mode ablation
    python -m benchmark.run_benchmark --report latex
"""

__version__ = "0.1.0"

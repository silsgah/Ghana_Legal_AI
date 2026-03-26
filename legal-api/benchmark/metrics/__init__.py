"""Metrics subpackage for LegalBench-GH evaluation."""

from benchmark.metrics.standard import get_standard_metrics
from benchmark.metrics.legal import get_legal_metrics

__all__ = ["get_standard_metrics", "get_legal_metrics"]

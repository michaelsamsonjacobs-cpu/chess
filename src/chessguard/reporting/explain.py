"""Utilities for turning detection outputs into human readable reports."""

from __future__ import annotations

from typing import Iterable

from ..pipeline.detection import DetectionReport


def format_model_section(name: str, report: DetectionReport) -> str:
    result = report.model_results[name]
    lines = [f"Model: {name}", f"  Score: {result.score:.2f}"]
    for factor in result.factors:
        lines.append(f"  - {factor}")
    return "\n".join(lines)


def generate_text_report(report: DetectionReport) -> str:
    lines = [
        f"Aggregate risk score: {report.aggregate_score:.2f}",
        f"Recommended action: {report.recommended_action}",
        "",
        "Model breakdown:",
    ]
    for name in report.model_results:
        lines.append(format_model_section(name, report))
    lines.append("")
    lines.append("Top features:")
    for name, value in sorted(report.features.items(), key=lambda item: abs(item[1]), reverse=True)[:10]:
        lines.append(f"  - {name}: {value:.3f}")
    return "\n".join(lines)

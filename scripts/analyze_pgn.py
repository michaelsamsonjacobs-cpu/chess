#!/usr/bin/env python3
"""Example CLI for running the ChessGuard pipeline on PGN data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import chess

from chessguard.pipeline import AnalysisPipeline
from chessguard.config import PipelineConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pgn",
        help=(
            "Path to a PGN file or an inline PGN/move sequence.  When the value "
            "does not correspond to an existing file it is interpreted as a literal string."
        ),
    )
    parser.add_argument(
        "--fen",
        help="Override the initial FEN before the first move is played.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Analyse games without a result (e.g., unfinished or aborted games).",
    )
    parser.add_argument(
        "--no-postprocess",
        action="store_true",
        help="Disable post-processing summaries and return the raw engine output.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print the raw JSON payload in addition to the textual summary.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of suspicious moves to display in the summary (default: 5).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path where the JSON output should be stored.",
    )
    return parser.parse_args()


def detect_source(pgn_arg: str) -> Any:
    candidate = Path(pgn_arg)
    if candidate.exists():
        return candidate
    return pgn_arg


def build_pipeline(args: argparse.Namespace) -> AnalysisPipeline:
    config = PipelineConfig(
        allow_incomplete_games=args.allow_incomplete,
        postprocess=not args.no_postprocess,
        extra_metadata={"cli": "analyze_pgn"},
    )
    return AnalysisPipeline(config=config)


def summarise(result: Dict[str, Any], top: int) -> str:
    lines = [
        "ChessGuard analysis summary",
        "==========================",
        f"Cheat likelihood:        {result.get('cheat_likelihood', 0.0):.3f}",
        f"Aggregate move score:    {result.get('aggregate_score', 0.0):.3f}",
        f"Suspicious move ratio:   {result.get('suspicious_ratio', 0.0):.3f}",
        "Minimum sample size met: "
        + ("yes" if result.get("minimum_sample_size_met") else "no"),
    ]

    metadata = result.get("metadata")
    if metadata:
        lines.append("Metadata: " + ", ".join(f"{key}={value}" for key, value in metadata.items()))

    moves = result.get("moves", [])
    suspicious = [move for move in moves if move.get("is_suspicious")]
    suspicious.sort(key=lambda m: m.get("smoothed_score", m.get("score", 0.0)), reverse=True)
    if suspicious:
        lines.append("")
        lines.append("Top suspicious moves:")
        for move in suspicious[: max(top, 0)]:
            lines.append(
                f"ply {move.get('ply'):>2} ({move.get('player')}): "
                f"{move.get('san')} | score={move.get('smoothed_score', move.get('score', 0.0)):.3f}"
            )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    pipeline = build_pipeline(args)
    source = detect_source(args.pgn)

    board, moves, extracted_metadata = pipeline.preprocess(source)
    metadata: Dict[str, Any] = dict(pipeline.config.extra_metadata)
    metadata.update(extracted_metadata)
    if args.fen:
        board = chess.Board(args.fen)
        metadata["fen_override"] = args.fen

    result = pipeline.inference(board, moves, metadata=metadata)
    result = pipeline.postprocess(result)

    summary = summarise(result, args.top)
    print(summary)

    if args.raw or args.output:
        payload = json.dumps(result, indent=2)
        if args.raw:
            print("\nRaw output:")
            print(payload)
        if args.output:
            args.output.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()

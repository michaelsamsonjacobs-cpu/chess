"""Utilities for enriching chess games with labels and engine-like scores."""
from __future__ import annotations

import datetime as _dt
import logging
import re
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Protocol, Sequence, Tuple

logger = logging.getLogger(__name__)

MOVE_RESULT_TOKENS = {"1-0", "0-1", "1/2-1/2", "*"}
MOVE_NUMBER_PATTERN = re.compile(r"^\d+\.{1,3}$")
COMMENT_PATTERN = re.compile(r"^\{.*\}$")


class EngineEvaluator(Protocol):
    """Protocol implemented by engine wrappers used for labelling."""

    def evaluate(self, game: Mapping[str, Any]) -> "EngineEvaluation":
        """Return an :class:`EngineEvaluation` for ``game``."""


@dataclass
class EngineEvaluation:
    """Summary of engine-style analysis for a single game."""

    average_centipawn_loss: float
    blunder_rate: float
    inaccuracy_rate: float
    move_count: int
    analysis_depth: int
    comment: str = ""
    per_move_scores: Optional[List[float]] = None

    def as_dict(self) -> Mapping[str, Any]:
        """Serialise the evaluation to a plain mapping."""

        payload = {
            "engine_average_centipawn_loss": self.average_centipawn_loss,
            "engine_blunder_rate": self.blunder_rate,
            "engine_inaccuracy_rate": self.inaccuracy_rate,
            "engine_move_count": self.move_count,
            "engine_analysis_depth": self.analysis_depth,
            "engine_comment": self.comment,
        }
        if self.per_move_scores is not None:
            payload["engine_per_move_scores"] = list(self.per_move_scores)
        return payload


@dataclass
class SimpleHeuristicEvaluator:
    """Fallback evaluator used when a stronger engine is unavailable.

    The heuristic looks for annotated move suffixes (``?``, ``??``, ``!``) to
    approximate quality.  While the signal is noisy, it provides a deterministic
    baseline suitable for tests and documentation examples.
    """

    depth: int = 18
    engine_id: str = "simple-heuristic-v1"

    def evaluate(self, game: Mapping[str, Any]) -> EngineEvaluation:
        moves_text = _extract_move_text(game)
        san_moves = _tokenise_san_moves(moves_text)
        move_count = len(san_moves)
        if move_count == 0:
            return EngineEvaluation(
                average_centipawn_loss=0.0,
                blunder_rate=0.0,
                inaccuracy_rate=0.0,
                move_count=0,
                analysis_depth=self.depth,
                comment="No moves parsed",
                per_move_scores=None,
            )

        blunders = sum(1 for move in san_moves if "??" in move)
        mistakes = sum(1 for move in san_moves if "?" in move and "??" not in move)
        brilliancies = sum(1 for move in san_moves if "!" in move and "!!" not in move)

        base_loss = 25.0 * mistakes + 60.0 * blunders
        average_centipawn_loss = max(0.0, base_loss / move_count)
        blunder_rate = blunders / move_count
        inaccuracy_rate = mistakes / move_count

        comment_parts = []
        if blunders:
            comment_parts.append(f"{blunders} blunder{'s' if blunders != 1 else ''}")
        if mistakes:
            comment_parts.append(f"{mistakes} mistake{'s' if mistakes != 1 else ''}")
        if brilliancies:
            comment_parts.append(f"{brilliancies} brilliant move{'s' if brilliancies != 1 else ''}")
        if not comment_parts:
            comment_parts.append("No annotated mistakes found")

        per_move_scores: Optional[List[float]] = None
        if move_count:
            penalty = base_loss / move_count if move_count else 0.0
            per_move_scores = [max(0.0, penalty - (i * 0.1 * penalty)) for i in range(move_count)]

        return EngineEvaluation(
            average_centipawn_loss=average_centipawn_loss,
            blunder_rate=blunder_rate,
            inaccuracy_rate=inaccuracy_rate,
            move_count=move_count,
            analysis_depth=self.depth,
            comment="; ".join(comment_parts),
            per_move_scores=per_move_scores,
        )


@dataclass
class LabelingGuidelines:
    """Parameters governing how engine scores translate into labels."""

    suspicious_threshold: float = 25.0
    review_threshold: float = 45.0
    high_blunder_rate: float = 0.08
    min_moves: int = 20
    suspicious_label: str = "suspicious"
    review_label: str = "review"
    clean_label: str = "clean"
    short_game_label: str = "short_game"

    def label_game(self, evaluation: EngineEvaluation, game: Mapping[str, Any]) -> Tuple[str, str]:
        """Return ``(label, reason)`` for ``game`` based on ``evaluation``."""

        if evaluation.move_count < self.min_moves:
            return (
                self.short_game_label,
                f"Only {evaluation.move_count} moves analysed (< {self.min_moves})",
            )

        if evaluation.blunder_rate > self.high_blunder_rate:
            return (
                self.clean_label,
                f"Blunder rate {evaluation.blunder_rate:.3f} exceeds threshold {self.high_blunder_rate:.3f}",
            )

        if evaluation.average_centipawn_loss <= self.suspicious_threshold:
            return (
                self.suspicious_label,
                f"Average CPL {evaluation.average_centipawn_loss:.2f} <= {self.suspicious_threshold:.2f}",
            )

        if evaluation.average_centipawn_loss <= self.review_threshold:
            return (
                self.review_label,
                f"Average CPL {evaluation.average_centipawn_loss:.2f} <= {self.review_threshold:.2f}",
            )

        return (
            self.clean_label,
            f"Average CPL {evaluation.average_centipawn_loss:.2f} > {self.review_threshold:.2f}",
        )


def _extract_move_text(game: Mapping[str, Any]) -> str:
    """Return the move text from a PGN or JSON-style game mapping."""

    if "Moves" in game:
        return str(game["Moves"])
    if "pgn" in game:
        return str(game["pgn"])
    if "moves" in game and isinstance(game["moves"], str):
        return str(game["moves"])
    return ""


def _tokenise_san_moves(moves_text: str) -> List[str]:
    """Split a SAN move string into a list of tokens."""

    tokens: List[str] = []
    for raw in moves_text.replace("\n", " ").split():
        cleaned = raw.strip()
        if not cleaned or cleaned in MOVE_RESULT_TOKENS:
            continue
        if MOVE_NUMBER_PATTERN.match(cleaned):
            continue
        if cleaned.endswith(".") and cleaned[:-1].isdigit():
            continue
        if cleaned.replace(".", "").isdigit():
            continue
        if COMMENT_PATTERN.match(cleaned) or cleaned.startswith(";"):
            continue
        tokens.append(cleaned)
    return tokens


def enrich_with_engine_evaluations(
    games: Sequence[Mapping[str, Any]],
    evaluator: Optional[EngineEvaluator] = None,
    *,
    include_evaluations: bool = False,
) -> Sequence[Mapping[str, Any]] | Tuple[List[Mapping[str, Any]], List[EngineEvaluation]]:
    """Attach engine-style metrics to each game."""

    evaluator = evaluator or SimpleHeuristicEvaluator()
    enriched: List[Mapping[str, Any]] = []
    evaluations: List[EngineEvaluation] = []

    for game in games:
        evaluation = evaluator.evaluate(game)
        record = dict(game)
        record.update(evaluation.as_dict())
        record["engine_id"] = getattr(evaluator, "engine_id", evaluator.__class__.__name__)
        enriched.append(record)
        evaluations.append(evaluation)

    if include_evaluations:
        return enriched, evaluations
    return enriched


def annotate_games_with_labels(
    games: Sequence[Mapping[str, Any]],
    evaluator: Optional[EngineEvaluator] = None,
    guidelines: Optional[LabelingGuidelines] = None,
    reviewer: Optional[str] = None,
) -> List[Mapping[str, Any]]:
    """Enrich ``games`` with engine scores and human-style labels."""

    guidelines = guidelines or LabelingGuidelines()
    enriched, evaluations = enrich_with_engine_evaluations(
        games, evaluator=evaluator, include_evaluations=True
    )

    timestamp = _dt.datetime.utcnow().isoformat(timespec="seconds")
    annotated: List[Mapping[str, Any]] = []
    for record, evaluation in zip(enriched, evaluations):
        label, reason = guidelines.label_game(evaluation, record)
        labelled = dict(record)
        labelled["label"] = label
        labelled["label_reason"] = reason
        labelled["label_applied_at"] = timestamp
        if reviewer:
            labelled["label_reviewer"] = reviewer
        annotated.append(labelled)

    return annotated


__all__ = [
    "EngineEvaluation",
    "EngineEvaluator",
    "LabelingGuidelines",
    "SimpleHeuristicEvaluator",
    "annotate_games_with_labels",
    "enrich_with_engine_evaluations",
]

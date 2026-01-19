"""Feature extraction for games and telemetry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from ..data.telemetry import SessionTelemetry
from ..utils.pgn import PGNGame
from .timing import compute_timing_features

OPENING_BOOK = {
    ("e4", "e5", "Nf3", "Nc6", "Bb5"),  # Ruy Lopez
    ("d4", "d5", "c4", "e6", "Nc3"),  # Queen's Gambit Declined
    ("c4", "e5", "Nc3", "Nf6"),  # English
    ("e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6"),  # Sicilian Najdorf mainline prefix
    ("d4", "Nf6", "c4", "g6", "Nc3", "Bg7"),  # King's Indian
}


def _flatten_moves(game: PGNGame) -> List[str]:
    tokens: List[str] = []
    for record in game.moves:
        if record.white:
            tokens.append(record.white)
        if record.black:
            tokens.append(record.black)
    return tokens


def _ratio(predicate, values: Iterable[str]) -> float:
    values = list(values)
    return sum(1 for value in values if predicate(value)) / len(values) if values else 0.0


def _novelty_ply(tokens: List[str]) -> int:
    if not tokens:
        return 0
    prefixes = {line[:index] for line in OPENING_BOOK for index in range(1, len(line) + 1)}
    for index in range(len(tokens)):
        prefix = tuple(tokens[: index + 1])
        if prefix not in prefixes:
            return index + 1
    return len(tokens)


def extract_move_features(game: PGNGame) -> Dict[str, float]:
    tokens = _flatten_moves(game)
    white_tokens = [record.white for record in game.moves if record.white]
    black_tokens = [record.black for record in game.moves if record.black]

    features: Dict[str, float] = {}
    features["ply_count"] = float(len(tokens))
    features["move_count"] = float(len(game.moves))
    features["unique_move_ratio"] = len(set(tokens)) / len(tokens) if tokens else 0.0
    features["capture_rate"] = _ratio(lambda value: "x" in value, tokens)
    features["check_rate"] = _ratio(lambda value: "+" in value or "#" in value, tokens)
    features["promotion_rate"] = _ratio(lambda value: "=" in value, tokens)
    features["pawn_move_ratio"] = _ratio(lambda value: value[0] in "abcdefgh", tokens)
    features["piece_move_ratio"] = _ratio(lambda value: value[0] in "KQRBN", tokens)
    features["annotation_rate"] = _ratio(lambda value: "!" in value or "?" in value, tokens)
    features["white_capture_rate"] = _ratio(lambda value: "x" in value, white_tokens)
    features["black_capture_rate"] = _ratio(lambda value: "x" in value, black_tokens)
    features["white_check_rate"] = _ratio(lambda value: "+" in value or "#" in value, white_tokens)
    features["black_check_rate"] = _ratio(lambda value: "+" in value or "#" in value, black_tokens)

    if tokens:
        average_length = sum(len(token.replace("+", "").replace("#", "")) for token in tokens) / len(tokens)
    else:
        average_length = 0.0
    features["average_move_length"] = average_length

    novelty = _novelty_ply(tokens)
    features["novelty_ply"] = float(novelty)

    run_lengths: List[int] = []
    if tokens:
        current_run = 1
        for previous, current in zip(tokens, tokens[1:]):
            if previous == current:
                current_run += 1
            else:
                run_lengths.append(current_run)
                current_run = 1
        run_lengths.append(current_run)
    features["max_repetition_run"] = float(max(run_lengths) if run_lengths else 0)

    return features


@dataclass
class FeatureVector:
    """Collection of numeric features used by the detection models."""

    values: Dict[str, float] = field(default_factory=dict)

    def merge(self, other: Dict[str, float]) -> None:
        self.values.update(other)

    def as_dict(self) -> Dict[str, float]:
        return dict(self.values)


def build_feature_vector(game: PGNGame, telemetry: Optional[SessionTelemetry] = None) -> FeatureVector:
    vector = FeatureVector()
    vector.merge(extract_move_features(game))
    if telemetry:
        vector.merge(compute_timing_features(telemetry))
    else:
        vector.merge({
            "avg_time": 0.0,
            "avg_time_white": 0.0,
            "avg_time_black": 0.0,
            "std_time": 0.0,
            "long_pause_rate": 0.0,
            "short_burst_rate": 0.0,
            "pace_balance": 0.0,
            "burstiness": 0.0,
            "tempo_shift_score": 0.0,
        })
    vector.merge({
        "capture_balance": vector.values.get("white_capture_rate", 0.0) - vector.values.get("black_capture_rate", 0.0),
        "check_balance": vector.values.get("white_check_rate", 0.0) - vector.values.get("black_check_rate", 0.0),
    })
    return vector

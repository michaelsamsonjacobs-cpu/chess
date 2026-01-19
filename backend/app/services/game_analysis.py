"""Services implementing the game review pipeline."""

from __future__ import annotations

import io
import math
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

import chess.pgn

from ..repositories import AppRepositories
from ..schemas.common import RiskFlag, TimingStats
from ..schemas.game import GameAnalysis, GameFeatures, GameIngestRequest, GameReport
from ..utils.statistics import (
    linear_regression_slope,
    log_normal_variance,
    logistic,
    normalized_score,
    safe_mean,
    safe_median,
    safe_pstdev,
)


class GameService:
    """Service responsible for ingesting and analyzing chess games."""

    def __init__(self, repositories: AppRepositories) -> None:
        self._repositories = repositories

    def ingest_game(self, request: GameIngestRequest) -> GameAnalysis:
        """Analyze a game and persist the resulting record."""

        game_id = uuid4()
        analysis = self._analyze_game(game_id, request)
        self._repositories.games.create(request, analysis)
        return analysis

    def get_report(self, game_id: UUID) -> GameReport:
        """Return a human-readable report for a stored game."""

        record = self._repositories.games.get(game_id)
        features = record.analysis.features
        flags = record.analysis.flags
        summary = (
            f"Suspicion score {record.analysis.suspicion_score:.2f} with engine-match "
            f"top-1 {features.engine_match_rate_top1:.2f} and Hick–Hyman slope {features.hick_hyman_slope:.3f}."
        )
        return GameReport(
            game_id=game_id,
            features=features,
            suspicion_score=record.analysis.suspicion_score,
            summary=summary,
            flags=flags,
            audit=record.analysis.audit,
        )

    def _analyze_game(self, game_id: UUID, request: GameIngestRequest) -> GameAnalysis:
        """Internal helper performing feature extraction from PGN + timing data."""

        parsed_game = chess.pgn.read_game(io.StringIO(request.pgn))
        if parsed_game is None:
            raise ValueError("Unable to parse PGN for analysis.")

        board = parsed_game.board()
        move_timings = {timing.ply: timing.time_seconds for timing in request.move_timings or []}
        increments = {timing.ply: timing.increment_seconds for timing in request.move_timings or []}

        engine_like_scores: List[float] = []
        complexity_levels: List[float] = []
        rt_pairs: List[Tuple[float, float]] = []
        rt_values: List[Optional[float]] = []
        error_indices: List[int] = []
        flag_notes: List[RiskFlag] = []

        for ply_index, move in enumerate(parsed_game.mainline_moves(), start=1):
            legal_count = board.legal_moves.count()
            complexity = math.log2(legal_count + 1)
            is_capture = board.is_capture(move)
            gives_check = board.gives_check(move)
            promotion_bonus = 0.3 if move.promotion else 0.0

            # Estimate how engine-like a move is via heuristic signals.
            signal = 0.0
            signal += 0.35 if is_capture else -0.05
            signal += 0.25 if gives_check else 0.0
            signal += 0.2 * normalized_score(complexity, low=1.0, high=6.0)
            signal += promotion_bonus
            signal -= 0.05 * math.log2(legal_count + 1)

            engine_like_probability = logistic(signal)
            engine_like_scores.append(engine_like_probability)
            complexity_levels.append(complexity)

            rt_value = move_timings.get(ply_index)
            rt_values.append(rt_value)
            if rt_value is not None:
                rt_pairs.append((complexity, rt_value))

            is_low_quality = engine_like_probability < 0.35 and complexity > 3.5
            if is_low_quality:
                error_indices.append(ply_index)

            # Suspicion heuristics for flagging individual moves.
            if (
                engine_like_probability > 0.85
                and complexity > 3.0
                and (rt_value is not None and rt_value < max(0.8, 0.4 + (increments.get(ply_index) or 0.0)))
            ):
                flag_notes.append(
                    RiskFlag(
                        code="fast_precision",
                        message=(
                            f"Move {ply_index} was played very quickly despite high complexity (engine-like {engine_like_probability:.2f})."
                        ),
                        severity="high",
                        context={"ply": str(ply_index)},
                    )
                )

            board.push(move)

        if not engine_like_scores:
            raise ValueError("PGN did not contain any moves for analysis.")

        engine_top1 = safe_mean(engine_like_scores)
        engine_top3 = min(1.0, engine_top1 + 0.15)
        avg_complexity = safe_mean(complexity_levels)
        complexity_index = normalized_score(avg_complexity, low=1.0, high=6.5)

        rt_only_values = [value for value in rt_values if value is not None]
        average_rt = safe_mean(rt_only_values)
        speed_accuracy_frontier = min(1.0, engine_top1 / (average_rt + 0.75)) if rt_only_values else engine_top1 * 0.8
        hick_hyman = 0.0
        if len(rt_pairs) >= 2:
            complexities, rts = zip(*rt_pairs)
            hick_hyman = linear_regression_slope(list(complexities), list(rts))

        post_error_slowing = 0.0
        if error_indices:
            error_rts: List[float] = []
            post_error_rts: List[float] = []
            for index in error_indices:
                current_rt = rt_values[index - 1]
                next_rt = rt_values[index] if index < len(rt_values) else None
                if current_rt is not None:
                    error_rts.append(current_rt)
                if next_rt is not None:
                    post_error_rts.append(next_rt)
            if error_rts and post_error_rts:
                post_error_slowing = safe_mean(post_error_rts) - safe_mean(error_rts)

        log_variance = log_normal_variance(rt_only_values)
        rt_stats = TimingStats(
            mean=average_rt,
            median=safe_median(rt_only_values),
            std_dev=safe_pstdev(rt_only_values),
            count=len(rt_only_values),
        )

        midpoint = max(1, len(engine_like_scores) // 2)
        start_mean = safe_mean(engine_like_scores[:midpoint])
        end_mean = safe_mean(engine_like_scores[midpoint:])
        accuracy_trend = max(min((end_mean - start_mean) * 2.5, 1.0), -1.0)

        consistency_bonus = 1.0 - normalized_score(log_variance, low=0.01, high=0.9)
        suspicion_score = max(
            0.0,
            min(
                1.0,
                0.6 * engine_top1 + 0.25 * speed_accuracy_frontier + 0.15 * consistency_bonus,
            ),
        )

        total_moves = len(engine_like_scores)
        if suspicion_score > 0.75 and total_moves >= 20:
            flag_notes.append(
                RiskFlag(
                    code="elevated_profile_risk",
                    message="High engine-likeness and consistent speed detected across complex moves.",
                    severity="critical",
                )
            )

        features = GameFeatures(
            total_moves=total_moves,
            engine_match_rate_top1=engine_top1,
            engine_match_rate_top3=engine_top3,
            hick_hyman_slope=hick_hyman,
            post_error_slowing=post_error_slowing,
            speed_accuracy_frontier=speed_accuracy_frontier,
            log_normal_rt_variance=log_variance,
            average_reaction_time=average_rt,
            reaction_time_stats=rt_stats,
            complexity_index=complexity_index,
            accuracy_trend=accuracy_trend,
        )

        return GameAnalysis(
            game_id=game_id,
            features=features,
            suspicion_score=suspicion_score,
            flags=flag_notes,
        )


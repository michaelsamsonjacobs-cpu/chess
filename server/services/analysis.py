from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean, median, pstdev
from typing import Dict, List, Optional, Tuple

import chess
import chess.pgn
import requests
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, joinedload, selectinload

from server.analysis.pipeline import GameAnalysisPipeline as EngineGameAnalysisPipeline
from server.models.game import (
    EngineEvaluation as EngineEvaluationModel,
    Game,
    Investigation,
    InvestigationStatus,
    User,
)
from server.services.engine import EngineEvaluation as EngineScore, UCIEngineError, UCIEngineRunner
from server.services.ensemble_score import DetectionSignals, calculate_ensemble_score
from server.services.advanced_detection import (
    analyze_critical_moments,
    analyze_time_distribution,
    analyze_opening_repertoire,
    analyze_resignation_patterns,
    analyze_opponent_correlation,
    analyze_sessions
)
from server.services.opening_book import analyze_opening, calculate_adjusted_accuracy
from server.services.cheater_db import check_player, BanStatus

LOGGER = logging.getLogger(__name__)


@dataclass
class AnalysisMetrics:
    move_count: int
    blunder_count: int
    suspicious_moves: int
    average_evaluation: float
    evaluation_stdev: float
    max_score_drop: float
    accuracy_estimate: float
    average_centipawn_loss: float
    median_centipawn_loss: float
    engine_agreement: float      # Player matched engine's #1 move
    perfect_move_rate: float
    # Fields with defaults must come after fields without defaults
    top2_engine_agreement: float = 0.0  # Player matched engine's #1 OR #2 move
    complexity_score: float = 0.0
    sabotage_score: float = 0.0 # Score indicating likelihood of "toggling" (blunder then perfect)
    tom_score: float = 0.0    # Measure of how "unnatural" the moves are (visual saliency)
    tension_complexity: float = 0.0 # Average number of attacks/defenses
    timing_score: float = 0.0  # 0.0 = human-like timing, 1.0 = engine-like timing
    suspicion_score: float = 0.0 # Aggregate score
    flags: List[str] = field(default_factory=list)
    critical_vs_normal_gap: float = 0.0
    critical_moves_correct: int = 0
    critical_moves_total: int = 0
    normal_moves_correct: int = 0
    normal_moves_total: int = 0

    def to_dict(self) -> Dict[str, float]:
        return {
            "move_count": self.move_count,
            "blunder_count": self.blunder_count,
            "suspicious_moves": self.suspicious_moves,
            "average_evaluation": self.average_evaluation,
            "evaluation_stdev": self.evaluation_stdev,
            "max_score_drop": self.max_score_drop,
            "accuracy_estimate": self.accuracy_estimate,
            "average_centipawn_loss": self.average_centipawn_loss,
            "median_centipawn_loss": self.median_centipawn_loss,
            "engine_agreement": self.engine_agreement,
            "top2_engine_agreement": self.top2_engine_agreement,
            "perfect_move_rate": self.perfect_move_rate,
            "complexity_score": self.complexity_score,
            "sabotage_score": self.sabotage_score,
            "tom_score": self.tom_score,
            "tension_complexity": self.tension_complexity,
            "tension_complexity": self.tension_complexity,
            "timing_score": self.timing_score,
            "suspicion_score": self.suspicion_score,
            "flags": self.flags,
            "critical_vs_normal_gap": self.critical_vs_normal_gap,
            "critical_moves_correct": self.critical_moves_correct,
            "critical_moves_total": self.critical_moves_total,
            "normal_moves_correct": self.normal_moves_correct,
            "normal_moves_total": self.normal_moves_total,
        }


class LichessClient:
    """Minimal client for fetching PGN data from Lichess."""

    def __init__(self, base_url: str = "https://lichess.org", timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def fetch_game_pgn(self, lichess_id: str) -> str:
        url = f"{self.base_url}/game/export/{lichess_id}"
        params = {
            "moves": 1,
            "tags": 1,
            "clocks": 1,
            "evals": 0,
            "pgnInJson": 0,
        }
        response = self._session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.text


class GameAnalysisPipeline:
    """Pipeline responsible for ingesting Lichess games and producing engine heuristics."""

    BLUNDER_THRESHOLD = 150.0
    PERFECT_MOVE_THRESHOLD = 10.0
    ENGINE_MATCH_THRESHOLD = 30.0
    DEFAULT_ENGINE_DEPTH = 16
    MAX_LOSS_FOR_ACCURACY = 800.0

    def __init__(
        self,
        session: Session,
        lichess_client: Optional[LichessClient] = None,
        logger: Optional[logging.Logger] = None,
        *,
        engine_depth: Optional[int] = None,
        engine_movetime: Optional[int] = None,
    ):
        self.session = session
        self.lichess = lichess_client or LichessClient()
        self.logger = logger or LOGGER
        self.engine_depth = self._resolve_depth(engine_depth)
        self.engine_movetime = self._resolve_movetime(engine_movetime)

    def _resolve_depth(self, depth: Optional[int]) -> Optional[int]:
        if depth is not None:
            return depth if depth > 0 else None

        env_value = os.getenv("CHESSGUARD_ANALYSIS_DEPTH")
        if env_value is None or not env_value.strip():
            return self.DEFAULT_ENGINE_DEPTH

        try:
            parsed = int(env_value)
        except ValueError:
            self.logger.warning(
                "Invalid CHESSGUARD_ANALYSIS_DEPTH value '%s'; using default depth %s.",
                env_value,
                self.DEFAULT_ENGINE_DEPTH,
            )
            return self.DEFAULT_ENGINE_DEPTH

        return parsed if parsed > 0 else None

    def _resolve_movetime(self, movetime: Optional[int]) -> Optional[int]:
        if movetime is not None:
            return movetime if movetime > 0 else None

        env_value = os.getenv("CHESSGUARD_ANALYSIS_MOVETIME")
        if env_value is None or not env_value.strip():
            return None

        try:
            parsed = int(env_value)
        except ValueError:
            self.logger.warning(
                "Invalid CHESSGUARD_ANALYSIS_MOVETIME value '%s'; ignoring.", env_value
            )
            return None

        return parsed if parsed > 0 else None

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_game(self, lichess_id: str, *, force: bool = False, pgn_text: Optional[str] = None, source: str = "lichess") -> Tuple[Game, bool]:
        """Fetch and persist metadata for a game (Lichess or generic PGN)."""
        
        self.logger.debug("Ingesting game %s (source=%s, force=%s)", lichess_id, source, force)
        stmt = select(Game).where(Game.lichess_id == lichess_id).options(joinedload(Game.investigation))
        result = self.session.execute(stmt).scalars().first()
        created = result is None
        game = result

        if game and not force and game.pgn:
            # The game is already present and we are not forcing a refresh.
            self.logger.debug("Game %s already ingested; skipping refresh", lichess_id)
            if game.analysis_status in {InvestigationStatus.PENDING, InvestigationStatus.QUEUED}:
                game.analysis_status = InvestigationStatus.QUEUED
                if game.investigation:
                    game.investigation.status = InvestigationStatus.QUEUED
            return game, False

        if not pgn_text and source == "lichess":
            pgn_text = self.lichess.fetch_game_pgn(lichess_id)
        
        if not pgn_text:
            raise ValueError(f"No PGN provided for non-Lichess game {lichess_id}")

        chess_game = self._parse_game(pgn_text)

        white_user = self._get_or_create_user(
            chess_game.headers.get("White", "White"), chess_game.headers.get("WhiteId")
        )
        black_user = self._get_or_create_user(
            chess_game.headers.get("Black", "Black"), chess_game.headers.get("BlackId")
        )
        played_at = self._parse_game_datetime(chess_game)

        if game is None:
            game = Game(
                lichess_id=lichess_id,
                source=source,
                white_player=white_user,
                black_player=black_user,
                played_at=played_at,
                result=chess_game.headers.get("Result"),
                pgn=pgn_text,
                analysis_status=InvestigationStatus.QUEUED,
            )
            self.session.add(game)
            created = True
        else:
            game.white_player = white_user
            game.black_player = black_user
            game.played_at = played_at
            game.result = chess_game.headers.get("Result")
            game.pgn = pgn_text
            game.source = source # Update source just in case
            game.analysis_status = InvestigationStatus.QUEUED

        if game.investigation is None:
            game.investigation = Investigation(status=InvestigationStatus.QUEUED)
        else:
            game.investigation.status = InvestigationStatus.QUEUED
            game.investigation.summary = None
            game.investigation.details = None

        self.session.flush()
        return game, created

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def run_analysis(self, game_id: int, *, force: bool = False) -> Game:
        """Run heuristics/engine checks for the selected game."""

        game = self.session.execute(
            select(Game)
            .where(Game.id == game_id)
            .options(
                selectinload(Game.investigation),
                selectinload(Game.evaluations),
                selectinload(Game.white_player),
                selectinload(Game.black_player),
            )
        ).scalar_one_or_none()

        if game is None:
            raise NoResultFound(f"Game {game_id} not found")

        if not game.pgn or force:
            if game.source == "lichess":
                self.logger.debug("Refreshing PGN for game %s from Lichess", game.lichess_id)
                pgn_text = self.lichess.fetch_game_pgn(game.lichess_id)
                game.pgn = pgn_text
            elif not game.pgn:
                 # If we are here, we have a non-Lichess game with NO PGN. We can't do anything.
                 raise ValueError(f"No PGN available for external game {game.lichess_id} and source is not lichess ({game.source})")
            # If force=True but source != lichess, we preserve existing PGN unless we implement external fetching logic later.

        try:
            game.analysis_status = InvestigationStatus.ANALYZING
            if game.investigation:
                game.investigation.status = InvestigationStatus.ANALYZING
            self.session.flush()

            parsed = self._parse_game(game.pgn)
            evaluations, metrics = self._evaluate_game(game, parsed)

            # Clear existing evaluations
            self.session.query(EngineEvaluationModel).filter(
                EngineEvaluationModel.game_id == game.id
            ).delete()
            self.session.flush()

            for evaluation in evaluations:
                self.session.add(evaluation)

            investigation = game.investigation or Investigation(game=game)
            should_flag = self._should_flag(metrics)
            investigation.status = (
                InvestigationStatus.FLAGGED if should_flag else InvestigationStatus.COMPLETED
            )
            investigation.summary = self._build_summary(investigation.status, metrics)
            investigation.details = metrics.to_dict()
            game.investigation = investigation
            game.analysis_status = investigation.status
            self.session.flush()
            return game
        except UCIEngineError as exc:
            self.logger.exception("Engine analysis failed for game %s", game_id)
            if game.investigation is None:
                game.investigation = Investigation(status=InvestigationStatus.ERROR)
            game.investigation.status = InvestigationStatus.ERROR
            game.investigation.summary = f"Engine analysis failed: {exc}"
            game.analysis_status = InvestigationStatus.ERROR
            self.session.flush()
            raise
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.exception("Analysis failed for game %s", game_id)
            if game.investigation is None:
                game.investigation = Investigation(status=InvestigationStatus.ERROR)
            game.investigation.status = InvestigationStatus.ERROR
            game.investigation.summary = f"Analysis failed: {exc}"
            game.analysis_status = InvestigationStatus.ERROR
            self.session.flush()
            raise

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_game(self, pgn_text: str) -> chess.pgn.Game:
        handle = io.StringIO(pgn_text)
        game = chess.pgn.read_game(handle)
        if game is None:
            raise ValueError("Unable to parse PGN data")
        return game

    def _parse_game_datetime(self, game: chess.pgn.Game) -> Optional[datetime]:
        date_raw = game.headers.get("UTCDate") or game.headers.get("Date")
        time_raw = game.headers.get("UTCTime") or "00:00:00"
        if not date_raw or date_raw == "????.??.??":
            return None
        try:
            dt = datetime.strptime(f"{date_raw} {time_raw}", "%Y.%m.%d %H:%M:%S")
            return dt
        except ValueError:
            return None

    def _get_or_create_user(self, username: str, lichess_identifier: Optional[str]) -> User:
        handle = lichess_identifier or username
        stmt = select(User).where(User.username == username)
        existing = self.session.execute(stmt).scalars().first()
        if existing:
            if handle and not existing.lichess_username:
                existing.lichess_username = handle
            return existing
        user = User(username=username, lichess_username=handle)
        self.session.add(user)
        self.session.flush()
        return user

    def _create_engine_runner(self) -> UCIEngineRunner:
        return UCIEngineRunner()

    def _score_to_centipawn(self, evaluation: EngineScore) -> float:
        if evaluation.score_cp is not None:
            return float(evaluation.score_cp)
        if evaluation.mate_in is not None:
            direction = 1 if evaluation.mate_in > 0 else -1
            return float(direction * 100000)
        return 0.0

    def _calculate_complexity(self, board: chess.Board) -> float:
        """
        Estimate position complexity based on number of legal moves and piece tension.
        Simple heuristic: Amount of legal moves roughly correlates with calculation depth required.
        """
        return float(board.legal_moves.count())

    def _detect_sabotage(self, centipawn_losses: List[float]) -> float:
        """
        Detect 'Sabotage' pattern: Big Blunder followed by a string of perfect moves.
        Returns a score 0.0 to 1.0.
        """
        score = 0.0
        consecutive_perfect = 0
        just_blundered = False

        for loss in centipawn_losses:
            if loss > self.BLUNDER_THRESHOLD:
                just_blundered = True
                consecutive_perfect = 0 # Reset streak on new blunder
            elif loss < self.PERFECT_MOVE_THRESHOLD:
                if just_blundered:
                    consecutive_perfect += 1
            else:
                # Normal move reset
                if consecutive_perfect > 3: # If we had a streak, keep that "memory" in the score
                     score += 0.2
                just_blundered = False
                consecutive_perfect = 0
        
        # Check if ended on a streak
        if consecutive_perfect > 3:
            score += 0.2

        return min(1.0, score)

    def _extract_move_times(self, pgn_game: chess.pgn.Game) -> List[float]:
        """
        Extract move times from PGN clock comments.
        
        PGN format: {[%clk 0:59:50]} or similar clock annotations.
        Returns list of time taken per move in seconds.
        """
        import re
        move_times = []
        prev_clock = None
        
        for node in pgn_game.mainline():
            # Look for clock comment in the node
            comment = node.comment
            clock_match = re.search(r'\[%clk (\d+):(\d+):(\d+(?:\.\d+)?)\]', comment)
            
            if clock_match:
                hours = int(clock_match.group(1))
                minutes = int(clock_match.group(2))
                seconds = float(clock_match.group(3))
                current_clock = hours * 3600 + minutes * 60 + seconds
                
                if prev_clock is not None:
                    # Time taken = previous clock - current clock
                    time_taken = prev_clock - current_clock
                    # Clamp to reasonable values (0-600 seconds)
                    time_taken = max(0.0, min(600.0, time_taken))
                    move_times.append(time_taken)
                
                prev_clock = current_clock
            else:
                # No clock data, use None placeholder
                if prev_clock is not None:
                    move_times.append(0.0)  # Unknown time
        
        return move_times

    def _calculate_timing_score(
        self, 
        move_times: List[float], 
        centipawn_losses: List[float],
        complexities: List[float]
    ) -> float:
        """
        Calculate timing suspicion score (0.0 = human-like, 1.0 = engine-like).
        
        Suspicious patterns detected:
        1. Flat timing - consistent move times regardless of position complexity
        2. Post-blunder pauses - long pauses right after making a blunder
        3. Fast complex moves - quick moves in highly complex positions
        4. Consistent narrow range - all moves within tight time band (e.g., 2-4s)
        5. Pre-move speed - extremely fast obvious moves (under 1s)
        """
        if not move_times or len(move_times) < 10:
            return 0.0  # Not enough data
        
        suspicion = 0.0
        valid_times = [t for t in move_times if t > 0]
        
        if len(valid_times) < 5:
            return 0.0
        
        # === 1. Flat timing detection ===
        # Humans vary their time; engines/cheaters are more consistent
        from statistics import mean, stdev
        avg_time = mean(valid_times)
        time_stdev = stdev(valid_times) if len(valid_times) > 1 else 0
        
        # Very low variance relative to mean is suspicious
        coefficient_of_variation = time_stdev / avg_time if avg_time > 0 else 0
        if coefficient_of_variation < 0.3:  # Less than 30% variation
            suspicion += 0.3
        
        # === 2. Post-blunder pause detection ===
        # Cheaters often pause after opponent blunders (to consult engine)
        post_blunder_pauses = 0
        for i in range(1, min(len(move_times), len(centipawn_losses))):
            if i > 0 and centipawn_losses[i-1] > 100:  # Previous move was a blunder
                if move_times[i] > avg_time * 2:  # Took extra long
                    post_blunder_pauses += 1
        
        if post_blunder_pauses >= 3:
            suspicion += 0.2
        
        # === 3. Fast moves in complex positions ===
        fast_complex = 0
        for i in range(min(len(move_times), len(complexities))):
            if complexities[i] > 35 and move_times[i] < 3.0:  # Complex but fast
                fast_complex += 1
        
        if fast_complex >= 5:
            suspicion += 0.25
        
        # === 4. Narrow time range (engine consulting) ===
        # Cheaters using engine often fall into 2-5 second range consistently
        narrow_band = sum(1 for t in valid_times if 2.0 <= t <= 5.0)
        if narrow_band / len(valid_times) > 0.7:  # 70%+ in narrow band
            suspicion += 0.2
        
        # === 5. Pre-move speed check ===
        # Some fast moves are normal (pre-moves), but too many is suspicious
        very_fast = sum(1 for t in valid_times if t < 0.5)
        if very_fast / len(valid_times) > 0.3:  # 30%+ instant moves
            # Could be pre-moves in time trouble, only suspicious with other flags
            if coefficient_of_variation < 0.4:
                suspicion += 0.1
        
        return min(1.0, suspicion)


    def _accuracy_from_loss(self, loss: float) -> float:
        if loss <= 0:
            return 1.0
        capped = min(loss, self.MAX_LOSS_FOR_ACCURACY)
        accuracy = 1.0 - (capped / self.MAX_LOSS_FOR_ACCURACY)
        return max(0.0, min(1.0, accuracy))

    def _calculate_tom_score(self, move: chess.Move, board: chess.Board, cp_gain: float) -> float:
        """
        Calculate the 'Vieth Score' (Visual Invisibility Score).
        Formula: (Centipawn Gain * Invisibility Factor) / 100
        
        Invisibility Factors:
        - Check/Capture: 0.1 (Highly visible)
        - Forward Move: 0.5 (Normal visibility)
        - Backward Linear (Rook/Queen retreat): 0.8 (Low visibility)
        - Backward Diagonal (Bishop/Queen retreat): 1.0 (Lowest visibility - Template Breaker)
        """
        if cp_gain < 10: # Irrelevant move
            return 0.0
        
        # 1. Determine Visibility
        is_capture = board.is_capture(move)
        is_check = board.gives_check(move)
        
        if is_capture or is_check:
            visibility_factor = 0.1
        else:
            # Analyze geometry
            from_rank = chess.square_rank(move.from_square)
            to_rank = chess.square_rank(move.to_square)
            from_file = chess.square_file(move.from_square)
            to_file = chess.square_file(move.to_square)
            
            is_backward = (board.turn == chess.WHITE and to_rank < from_rank) or \
                          (board.turn == chess.BLACK and to_rank > from_rank)
            
            is_diagonal = abs(from_rank - to_rank) == abs(from_file - to_file)
            
            if is_backward:
                visibility_factor = 1.0 if is_diagonal else 0.8
            else:
                visibility_factor = 0.5

        # 2. Calculate Score
        # We cap CP gain at 500 to avoid skewing by massive blunders/mates
        score = (min(cp_gain, 500) * visibility_factor) / 100.0
        return score

    def _count_tension(self, board: chess.Board) -> int:
        """Count total number of attacks currently on the board."""
        # Simple heuristic: sum of all attacks for all pieces
        total_attacks = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                total_attacks += len(board.attacks(square))
        return total_attacks

    def _evaluate_game(
        self, game: Game, parsed_game: chess.pgn.Game
    ) -> Tuple[List[EngineEvaluationModel], AnalysisMetrics]:
        with self._create_engine_runner() as engine:
            pipeline = EngineGameAnalysisPipeline(
                engine,
                depth=self.engine_depth,
                movetime=self.engine_movetime,
            )
            analysis = pipeline.analyse_game(parsed_game, game_id=game.lichess_id)

        evaluations: List[EngineEvaluationModel] = []
        centipawn_losses: List[float] = []
        evaluation_scores: List[float] = []
        blunder_count = 0
        perfect_moves = 0
        accuracy_total = 0.0
        top2_matches = 0  # Track moves matching 1st or 2nd best

        for move in analysis.moves:
            cp_loss = float(move.centipawn_loss or 0)
            centipawn_losses.append(cp_loss)

            played_score = self._score_to_centipawn(move.played)
            evaluation_scores.append(played_score)

            best_move = move.best.bestmove or (move.best.pv[0] if move.best.pv else None)

            is_blunder = cp_loss >= self.BLUNDER_THRESHOLD
            is_perfect = cp_loss <= self.PERFECT_MOVE_THRESHOLD

            if is_blunder:
                blunder_count += 1
            if is_perfect:
                perfect_moves += 1

            accuracy = self._accuracy_from_loss(cp_loss)
            accuracy_total += accuracy
            
            # Track if move matches top-2 engine recommendations
            # A move is considered "top-2" if its centipawn loss is very low (< 20cp)
            # This includes both exact matches and moves that are nearly as good
            TOP2_THRESHOLD = 20.0  # cp threshold for "practically as good"
            if cp_loss <= TOP2_THRESHOLD:
                top2_matches += 1

            # Reconstruct board to calculate complexity (expensive, but necessary for this feature)
            # Optimization: logic relies on parsed_game iteration sequence matching analysis.moves
            # We will approximate complexity average later or do it here if we have the board state.
            
            # Note: analysis.moves doesn't carry the board state. We'd need to replay the game.
            # For now, let's skip per-move complexity to avoid re-parsing overhead in this loop 
            # and just use the sabotage detector which operates on the loss array.
            
            evaluation = EngineEvaluationModel(
                game=game,
                move_number=move.ply,
                evaluation_cp=played_score,
                best_move=best_move,
                accuracy=round(accuracy, 3),
                flagged=is_blunder,
                extra_metadata={
                    "centipawn_loss": cp_loss,
                    "player": move.player,
                    "move_number": move.move_number,
                    "move_san": move.move_san,
                    "move_uci": move.move_uci,
                    "best": move.best.to_dict(),
                    "played": move.played.to_dict(),
                },
            )
            evaluations.append(evaluation)
        
        # Replay game to calculate complexity and Vieth scores
        board = parsed_game.board()
        tom_scores = []
        tension_scores = []
        
        # Iterate over mainline moves. Note: analysis.moves should match mainline
        # We zip them to have both move info and engine info
        for node, analysis_move in zip(parsed_game.mainline(), analysis.moves):
            move = node.move
            
            # Pre-move tension
            tension_scores.append(self._count_tension(board))
            
            # Calculate Vieth Score for the move played
            # We use 'played' score improvement? No, Vieth score is about "finding a good move that is invisible".
            # So if the move played was GOOD (low centipawn loss), and invisible, it scores high.
            # If the move was bad, it doesn't matter if it was invisible.
            # Actually, the formula uses "CP Gain". A good move gains CP (relative to previous bad eval) or maintains it.
            # But standard CP loss is "how much usually worse than best".
            # A "Quiet Killer" is best_move with high impact.
            # Let's use: (Best Move Score - Pre-Move Eval)? 
            # Or simplified: If move is PERFECT (low CPL) and invisible, we score it.
            
            cp_loss = float(analysis_move.centipawn_loss or 0)
            if cp_loss < self.PERFECT_MOVE_THRESHOLD:
                # How much better is this position than the previous one?
                # Actually, engine evaluation is static.
                # Let's just use a fixed "Impact Strength" of 100 for perfect moves, 
                # scaled by invisibility.
                v_score = self._calculate_tom_score(move, board, 100.0)
                tom_scores.append(v_score)
            else:
                tom_scores.append(0.0)
                
            board.push(move)

        move_count = len(centipawn_losses)
        average_eval = mean(evaluation_scores) if evaluation_scores else 0.0
        evaluation_stdev = (
            pstdev(evaluation_scores) if len(evaluation_scores) > 1 else 0.0
        )
        average_cp_loss = mean(centipawn_losses) if centipawn_losses else 0.0
        median_cp_loss = median(centipawn_losses) if centipawn_losses else 0.0
        max_cp_loss = max(centipawn_losses) if centipawn_losses else 0.0
        engine_agreement = (
            sum(1 for loss in centipawn_losses if loss <= self.ENGINE_MATCH_THRESHOLD)
            / move_count
            if move_count
            else 0.0
        )
        accuracy_estimate = (
            accuracy_total / move_count if move_count else 1.0
        )
        perfect_rate = perfect_moves / move_count if move_count else 0.0
        
        avg_tom = mean(tom_scores) if tom_scores else 0.0
        avg_tension = mean(tension_scores) if tension_scores else 0.0
        
        # Calculate top-2 engine agreement (moves within 20cp of best)
        top2_engine_agreement = top2_matches / move_count if move_count else 0.0
        
        # Calculate sabotage score (blunder then perfect play pattern)
        sabotage_score = self._detect_sabotage(centipawn_losses)
        
        # Extract move times and calculate timing suspicion
        move_times = self._extract_move_times(parsed_game)
        timing_score = self._calculate_timing_score(move_times, centipawn_losses, tension_scores)
        
        # --- V2 DETECTION SIGNALS CONSTRUCTION ---
        
        # 0. Book Move Filtering (NEW)
        opening_analysis = analyze_opening(game.pgn, player_color)
        moves_in_book = opening_analysis.moves_in_book if opening_analysis else 0
        adj_engine_agreement = calculate_adjusted_accuracy(
            [1.0 if loss <= self.ENGINE_MATCH_THRESHOLD else 0.0 for loss in centipawn_losses],
            moves_in_book
        )

        # 1. Sniper Index (Critical Moment Analysis)
        # We need to reconstruct the critical moment stats from the moves list
        s_crit_correct = 0
        s_crit_total = 0
        s_norm_correct = 0
        s_norm_total = 0
        
        for m in analysis.moves:
            # Check if we have MultiPV info
            if hasattr(m.best, "multipv_info") and len(m.best.multipv_info) >= 2:
                # We have at least 2 lines!
                # pv1 = m.best.multipv_info[0]
                # pv2 = m.best.multipv_info[1]
                # But wait, m.best is an EngineEvaluation object.
                # multipv_info is a list of dicts.
                info1 = m.best.multipv_info[0]
                info2 = m.best.multipv_info[1]
                
                score1 = info1.get("score_cp")
                score2 = info2.get("score_cp")
                
                if score1 is not None and score2 is not None:
                     # Calculate diff (Sniper Criticality)
                     diff = abs((score1 - score2) / 100.0)
                     abs_score = abs(score1 / 100.0)
                     
                     # Is Balanced? (<= 2.0)
                     is_balanced = abs_score <= 2.0
                     
                     # Is Critical? (Diff > 0.75)
                     is_critical = is_balanced and diff > 0.75
                     
                     # Did they play the best move?
                     # Simple check: was centipawn loss near zero?
                     is_best = (m.centipawn_loss or 0) < self.PERFECT_MOVE_THRESHOLD
                     
                     if is_critical:
                         s_crit_total += 1
                         if is_best: s_crit_correct += 1
                     else:
                         s_norm_total += 1
                         if is_best: s_norm_correct += 1
            else:
                # Fallback if no MultiPV (shouldn't happen with updated pipeline)
                pass

        # Calculate Sniper Gaps for this game
        # V2 FIX: Require minimum 5 critical moves to calculate a gap,
        # avoiding false positives from small samples (e.g. 1/1 = 100%).
        crit_acc = 0.0
        norm_acc = 0.0
        sniper_gap = 0.0
        
        if s_crit_total >= 5:
            crit_acc = s_crit_correct / s_crit_total
            norm_acc = s_norm_correct / s_norm_total if s_norm_total > 0 else 0.0
            sniper_gap = crit_acc - norm_acc
        
        # 2. Known Cheater Check
        is_known = False
        ban_status = check_player(
            self.session, 
            game.white_player.username if game.white_player else "", 
            game.source if game.source else "chesscom"
        )
        if ban_status and ban_status.is_banned: 
            is_known = True

        # 3. Streak Metrics (Placeholder for single game)
        # In a real pipeline, we'd query historical games here.
        # For this Game Analysis object, we'll leave it 0, but it will be aggregated later.
        
        signals = DetectionSignals(
            engine_agreement=engine_agreement,
            adjusted_engine_agreement=adj_engine_agreement,
            moves_in_book=moves_in_book,
            timing_suspicion=timing_score,
            scramble_toggle_score=sabotage_score, 
            streak_improbability_score=0.0, # Need history
            streak_density=0.0, # Need history
            
            critical_vs_normal_gap=sniper_gap,
            critical_moves_correct=s_crit_correct,
            critical_moves_total=s_crit_total,
            normal_moves_correct=s_norm_correct,
            normal_moves_total=s_norm_total,
            
            is_known_cheater=is_known,
            games_analyzed=1,
            high_accuracy_games_count=1 if perfect_rate > 0.95 else 0
        )
        
        # Calculate V2 Score
        ensemble_result = calculate_ensemble_score(signals)
        suspicion_score = ensemble_result.ensemble_score / 100.0 # Normalize to 0-1 for compatibility
        
        metrics = AnalysisMetrics(
            move_count=move_count,
            blunder_count=blunder_count,
            suspicious_moves=perfect_moves,
            average_evaluation=round(average_eval, 2),
            evaluation_stdev=round(evaluation_stdev, 2),
            max_score_drop=round(max_cp_loss, 2),
            accuracy_estimate=round(accuracy_estimate, 3),
            average_centipawn_loss=round(average_cp_loss, 2),
            median_centipawn_loss=round(median_cp_loss, 2),
            engine_agreement=round(engine_agreement, 3),
            top2_engine_agreement=round(top2_engine_agreement, 3),
            perfect_move_rate=round(perfect_rate, 3),
            complexity_score=0.0, # Placeholder
            sabotage_score=round(sabotage_score, 2),
            tom_score=round(avg_tom, 2),
            tension_complexity=round(avg_tension, 2),
            timing_score=round(timing_score, 2),
            suspicion_score=round(suspicion_score, 2),
            flags=ensemble_result.flags,
            critical_vs_normal_gap=round(sniper_gap, 3),
            critical_moves_correct=s_crit_correct,
            critical_moves_total=s_crit_total,
            normal_moves_correct=s_norm_correct,
            normal_moves_total=s_norm_total,
        )
        return evaluations, metrics

    def _should_flag(self, metrics: AnalysisMetrics) -> bool:
        if metrics.move_count < 20:
            return False
        if metrics.blunder_count > 1:
            return False
        if metrics.max_score_drop > 200:
            return False
        if metrics.suspicion_score > 0.6:
            return True
        if metrics.sabotage_score > 0.1:
            return True

        # Fallback to legacy checks if scores are borderline
        if metrics.average_centipawn_loss > 25 and metrics.engine_agreement < 0.85:
            return False
            
        return True

    def _build_summary(self, status: InvestigationStatus, metrics: AnalysisMetrics) -> str:
        if status == InvestigationStatus.FLAGGED:
            agreement_pct = metrics.engine_agreement * 100
            return (
                "High engine agreement detected: "
                f"{agreement_pct:.0f}% of moves within {int(self.ENGINE_MATCH_THRESHOLD)} cp "
                f"and {metrics.suspicious_moves} near-perfect plays across {metrics.move_count} plies."
            )
        
        if metrics.flags:
            return f"Flagged by V2 Model: {', '.join(metrics.flags)}"

        return (
            f"Analysis complete: {metrics.blunder_count} blunders, average CPL {metrics.average_centipawn_loss:.1f}, "
            f"engine agreement {metrics.engine_agreement * 100:.0f}%."
        )

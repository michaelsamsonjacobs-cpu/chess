from __future__ import annotations

import os
from typing import Optional

from celery import Celery

from server.database import session_scope
from server.services.analysis import GameAnalysisPipeline


CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "memory://")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "rpc://")

celery_app = Celery("chessguard", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=os.getenv("CELERY_TASK_ALWAYS_EAGER", "1") == "1",
    task_eager_propagates=True,
)


@celery_app.task(name="chessguard.analyze_game")
def analyze_game_task(game_id: int, force: bool = False) -> Optional[int]:
    """Celery task that performs a full analysis for the given game."""

    with session_scope() as session:
        pipeline = GameAnalysisPipeline(session=session)
        game = pipeline.run_analysis(game_id=game_id, force=force)
        return game.id if game else None


def enqueue_game_analysis(game_id: int, force: bool = False) -> None:
    """Submit the game for background analysis."""

    analyze_game_task.delay(game_id, force=force)


@celery_app.task(name="chessguard.batch_analyze")
def batch_analyze_task(batch_id: int, source: str, username: str, timeframe: str = "1m") -> dict:
    """Celery task that performs batch analysis for all games of a player."""
    import httpx
    import asyncio
    from datetime import datetime
    from statistics import mean
    
    from server.models.game import (
        BatchAnalysis,
        BatchAnalysisStatus,
        RiskLevel,
        Game,
        InvestigationStatus,
    )
    
    with session_scope() as session:
        # Get batch record
        batch = session.query(BatchAnalysis).filter(BatchAnalysis.id == batch_id).first()
        if not batch:
            return {"error": f"Batch {batch_id} not found"}
        
        batch.status = BatchAnalysisStatus.RUNNING
        session.commit()
        
        try:
            # Fetch games based on source and timeframe
            games_data = []
            
            # Map timeframe to months/max_games
            timeframe_map = {
                "1m": {"months": 1, "games": 50},
                "3m": {"months": 3, "games": 150},
                "6m": {"months": 6, "games": 300},
                "12m": {"months": 12, "games": 600},
                "all": {"months": 999, "games": 1000}
            }
            window = timeframe_map.get(timeframe, timeframe_map["1m"])
            
            # Create a new event loop for this thread (required for asyncio.run in threads)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                if source == "lichess":
                    # Fetch from Lichess public API
                    url = f"https://lichess.org/api/games/user/{username}"
                    headers = {"Accept": "application/x-ndjson", "User-Agent": "ChessGuard/1.0"}
                    
                    async def fetch_lichess():
                        async with httpx.AsyncClient(timeout=60.0) as client:
                            params = {"max": window["games"], "pgnInJson": "true"}
                            async with client.stream("GET", url, headers=headers, params=params) as resp:
                                result = []
                                async for line in resp.aiter_lines():
                                    if line.strip():
                                        import json
                                        result.append(json.loads(line))
                                return result
                    
                    games_data = loop.run_until_complete(fetch_lichess())
                    
                elif source == "chesscom":
                    from server.services.chesscom import chesscom_service
                    games_data = loop.run_until_complete(chesscom_service.get_recent_games(username, limit_months=window["months"]))
            finally:
                loop.close()
            
            batch.total_games = len(games_data)
            session.commit()
            
            if not games_data:
                batch.status = BatchAnalysisStatus.COMPLETED
                batch.completed_at = datetime.utcnow()
                batch.error_message = f"No games found for player '{username}' in the requested period."
                session.commit()
                return
            
            # Analyze each game
            pipeline = GameAnalysisPipeline(session=session)
            suspicion_scores = []
            flagged_count = 0
            all_games = games_data  # Keep reference for streak analysis
            timing_suspicions = []
            complexity_scores_all = []
            engine_agreements = []
            adjusted_agreements = []
            
            # Import new analyzers
            try:
                from server.services.timing_analysis import analyze_game_timing
                from server.services.opening_book import analyze_opening, calculate_adjusted_accuracy
                from server.services.complexity_analysis import analyze_game_complexity, get_complexity_stats
                from server.services.ensemble_score import DetectionSignals, calculate_ensemble_score
                from server.services.advanced_detection import (
                    analyze_opening_repertoire,
                    analyze_resignation_patterns,
                    analyze_opponent_correlation,
                    analyze_sessions,
                    analyze_critical_moments,
                    analyze_time_distribution
                )
                has_advanced_analysis = True
            except ImportError as e:
                print(f"Advanced analysis modules not available: {e}")
                has_advanced_analysis = False
            
            for i, game_data in enumerate(games_data):
                try:
                    # Extract game info
                    if source == "lichess":
                        game_id_str = game_data.get("id", f"lichess_{i}")
                        pgn = game_data.get("pgn", "")
                    else:
                        game_id_str = game_data.get("url", "").split("/")[-1] or f"chesscom_{i}"
                        pgn = game_data.get("pgn", "")
                    
                    if not pgn:
                        continue
                    
                    # Ingest and analyze
                    game, _ = pipeline.ingest_game(
                        lichess_id=game_id_str,
                        pgn_text=pgn,
                        source=source,
                        force=False
                    )
                    game.batch_id = batch_id
                    session.commit()
                    
                    # Run engine analysis
                    analyzed_game = pipeline.run_analysis(game_id=game.id, force=False)
                    
                    # Track basic metrics
                    if analyzed_game.investigation and analyzed_game.investigation.details:
                        score = analyzed_game.investigation.details.get("suspicion_score", 0)
                        engine_agreement = analyzed_game.investigation.details.get("engine_agreement", 0)
                        suspicion_scores.append(score)
                        engine_agreements.append(engine_agreement)
                        if score > 0.5:
                            flagged_count += 1
                    
                    # Advanced analysis (if available)
                    if has_advanced_analysis and pgn:
                        # Determine player color
                        player_color = "white"  # Default
                        if source == "chesscom":
                            white_player = game_data.get("white", {})
                            if isinstance(white_player, dict):
                                if white_player.get("username", "").lower() != username.lower():
                                    player_color = "black"
                        
                        # Timing analysis
                        timing_metrics = analyze_game_timing(game_data, username, source)
                        if timing_metrics:
                            timing_suspicions.append(timing_metrics.timing_suspicion_score)
                        
                        # Opening book analysis
                        opening = analyze_opening(pgn, player_color)
                        if opening and len(engine_agreements) > 0:
                            # Calculate adjusted accuracy excluding book moves
                            moves_in_book = opening.moves_in_book
                            # For now, use a simple adjustment factor
                            if moves_in_book > 0 and engine_agreement > 0:
                                adjusted = calculate_adjusted_accuracy(
                                    [engine_agreement] * 30,  # Simplified
                                    moves_in_book
                                )
                                adjusted_agreements.append(adjusted)
                        
                        # Complexity analysis
                        complexity_list = analyze_game_complexity(pgn, player_color)
                        if complexity_list:
                            complexity_scores_all.extend(complexity_list)
                        
                        # Store for aggregate analysis
                        game_data["analyzed_metrics"] = analyzed_game.investigation.details if analyzed_game.investigation else {}
                        game_data["player_color"] = player_color
                    
                    batch.analyzed_count = i + 1
                    
                    # Update aggregate suspicion incrementally
                    if suspicion_scores:
                        batch.avg_suspicion = round(mean(suspicion_scores), 3)
                        batch.flagged_count = flagged_count
                    
                    session.commit()
                    
                except Exception as e:
                    print(f"Error analyzing game {i}: {e}")
                    continue
            
            # Calculate aggregates
            avg_suspicion = mean(suspicion_scores) if suspicion_scores else 0.0
            flagged_pct = (flagged_count / batch.total_games * 100) if batch.total_games else 0
            avg_timing = mean(timing_suspicions) if timing_suspicions else 0.0
            avg_complexity = mean(complexity_scores_all) if complexity_scores_all else 0.0
            avg_engine = mean(engine_agreements) if engine_agreements else 0.0
            avg_adjusted = mean(adjusted_agreements) if adjusted_agreements else avg_engine
            
            # Run streak improbability analysis
            streak_score = 0.0
            longest_streak = 0
            try:
                from server.services.streak_analysis import analyze_streaks
                streak_result = analyze_streaks(all_games, username)
                batch.longest_win_streak = streak_result.longest_win_streak
                batch.streak_improbability_score = streak_result.streak_improbability_score
                batch.suspicious_streak_count = len(streak_result.suspicious_streaks)
                batch.max_streak_improbability = streak_result.max_improbability
                streak_score = streak_result.streak_improbability_score
                longest_streak = streak_result.longest_win_streak
            except Exception as streak_error:
                print(f"Streak analysis failed: {streak_error}")
            
            # Calculate ensemble score
            ensemble_result = None
            if has_advanced_analysis:
                try:
                    # Prepare game summaries for aggregate signals
                    games_for_adv = []
                    for g in games_data:
                        m = g.get("analyzed_metrics", {})
                        if not m: continue
                        games_for_adv.append({
                            "opening": m.get("opening_name", "Unknown"),
                            "moves": [{"accuracy": acc} for acc in m.get("move_accuracies", [])], # Approximation
                            "result": g.get("result", ""),
                            "termination": g.get("termination", ""),
                            "is_player_win": g.get("result", "") == ("1-0" if g.get("player_color") == "white" else "0-1"),
                            "player_blundered": m.get("blunder_count", 0) > 0,
                            "player_accuracy": m.get("accuracy_estimate", 0.5),
                            "opponent_rating": g.get("white" if g.get("player_color") == "black" else "black", {}).get("rating", 1500),
                            "timestamp": g.get("end_time", 0) # Fallback
                        })

                    # Run Advanced Aggregate Analyzers
                    opening_adv = analyze_opening_repertoire(games_for_adv)
                    resignation_adv = analyze_resignation_patterns(games_for_adv)
                    opponent_adv = analyze_opponent_correlation(games_for_adv)
                    session_adv = analyze_sessions(games_for_adv)
                    
                    # Prepare all-moves list for session/time distribution
                    # This is complex because we'd need per-move data for all games.
                    # For now, we'll use the aggregated timing suspicion.

                    signals = DetectionSignals(
                        engine_agreement=avg_engine,
                        adjusted_engine_agreement=avg_adjusted,
                        moves_in_book=sum(g.get("analyzed_metrics", {}).get("moves_in_book", 0) for g in games_data),
                        timing_suspicion=avg_timing,
                        scramble_toggle_score=max([0] + [t for t in timing_suspicions if t > 0.5]),
                        uniform_timing_score=0.0,
                        streak_improbability_score=streak_score,
                        longest_win_streak=longest_streak,
                        complexity_accuracy_corr=None,  # Requires per-move correlation
                        avg_complexity=avg_complexity,
                        games_analyzed=batch.total_games,
                        flagged_games=flagged_count,
                        
                        # Add advanced signals
                        opening_repertoire_score=opening_adv.suspicious_score,
                        unique_openings_count=opening_adv.unique_openings,
                        resignation_pattern_score=resignation_adv.suspicious_score,
                        never_blunder_resign=resignation_adv.never_blunder_resign,
                        opponent_correlation_score=opponent_adv.suspicious_score,
                        rises_to_occasion=opponent_adv.rises_to_occasion,
                        session_fatigue_score=session_adv.suspicious_score,
                        never_tires=session_adv.never_tires
                    )
                    ensemble_result = calculate_ensemble_score(signals)
                    
                    # Use ensemble score for final risk determination
                    avg_suspicion = ensemble_result.ensemble_score / 100  # Normalize to 0-1
                except Exception as e:
                    print(f"Ensemble calculation failed: {e}")
            
            # Determine risk level based on ensemble or fallback
            if ensemble_result:
                risk_str = ensemble_result.risk_level
                risk = getattr(RiskLevel, risk_str.upper(), RiskLevel.LOW)
            else:
                if flagged_pct > 10 or avg_suspicion > 0.8:
                    risk = RiskLevel.CRITICAL
                elif flagged_pct > 5 or avg_suspicion > 0.5:
                    risk = RiskLevel.HIGH
                elif flagged_pct > 1 or avg_suspicion > 0.2:
                    risk = RiskLevel.MEDIUM
                else:
                    risk = RiskLevel.LOW
            
            batch.flagged_count = flagged_count
            batch.avg_suspicion = round(avg_suspicion, 3)
            batch.risk_level = risk
            batch.status = BatchAnalysisStatus.COMPLETED
            batch.completed_at = datetime.utcnow()
            session.commit()
            
            return {
                "batch_id": batch_id,
                "total_games": batch.total_games,
                "analyzed": batch.analyzed_count,
                "flagged": flagged_count,
                "risk_level": risk.value,
                "ensemble_score": ensemble_result.ensemble_score if ensemble_result else None,
                "timing_suspicion": round(avg_timing, 3),
                "complexity_avg": round(avg_complexity, 3),
            }
            
        except Exception as e:
            batch.status = BatchAnalysisStatus.ERROR
            batch.error_message = str(e)
            session.commit()
            return {"error": str(e)}


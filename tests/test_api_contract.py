"""Contract tests for the service layer."""

from __future__ import annotations

import pytest

from chessguard import (
    ChessGuardEngine,
    ChessGuardService,
    TournamentEvaluationRequest,
    TournamentGameInput,
    load_default_model,
)


def test_service_returns_structured_response() -> None:
    engine = ChessGuardEngine(load_default_model(), alert_threshold=0.7)
    service = ChessGuardService(engine)
    request = TournamentEvaluationRequest(
        tournament_id="event-2023",
        games=[
            TournamentGameInput(
                game_id="alpha",
                moves=["e4", "e5", "Nf3", "Nc6", "Bb5", "a6"],
                result="1-0",
            ),
            TournamentGameInput(
                game_id="beta",
                moves=["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7"],
                result="1/2-1/2",
            ),
        ],
    )

    response = service.evaluate_tournament(request)

    assert response.tournament_id == "event-2023"
    assert len(response.evaluations) == len(request.games)
    assert 0.0 <= response.alert_rate <= 1.0
    assert set(response.summary.keys()) == {"games_evaluated", "alerts", "threshold"}
    assert response.summary["games_evaluated"] == pytest.approx(len(request.games))
    assert response.summary["threshold"] == pytest.approx(engine.alert_threshold)

    for evaluation, game in zip(response.evaluations, request.games, strict=True):
        assert evaluation.game_id == game.game_id
        assert 0.0 <= evaluation.probability <= 1.0
        assert isinstance(evaluation.alert, bool)

    metrics_blob = ChessGuardService.export_metrics().decode("utf-8")
    assert "chessguard_service_requests_total" in metrics_blob
    assert "evaluate_tournament" in metrics_blob

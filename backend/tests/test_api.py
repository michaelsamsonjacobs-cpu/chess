"""Integration tests covering key ChessGuard API flows."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


SAMPLE_PGN = """\
[Event "Casual Game"]
[Site "Berlin GER"]
[Date "1852.??.??"]
[Round "?"]
[White "Adolf Anderssen"]
[Black "Jean Dufresne"]
[Result "1-0"]

1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.b4 Bxb4 5.c3 Ba5 6.d4 exd4 7.O-O d3 8.Qb3 Qf6 9.e5 Qg6 10.Re1 Nge7 11.Ba3 b5 12.Qxb5 Rb8 13.Qa4 Bb6 14.Nbd2 Bb7 15.Ne4 Qf5 16.Bxd3 Qh5 17.Nf6+ gxf6 18.exf6 Rg8 19.Rad1 Qxf3 20.Rxe7+ Nxe7 21.Qxd7+ Kxd7 22.Bf5+ Ke8 23.Bd7+ Kf8 24.Bxe7# 1-0
"""


def test_game_ingestion_and_report() -> None:
    move_timings = [
        {"ply": index + 1, "time_seconds": 5.0 - (index * 0.1)} for index in range(12)
    ]
    response = client.post(
        "/games/ingest",
        json={
            "source": "upload",
            "pgn": SAMPLE_PGN,
            "player_id": "player-123",
            "move_timings": move_timings,
            "metadata": {"time_control": "5+0"},
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "analysis" in payload
    analysis = payload["analysis"]
    assert 0.0 <= analysis["suspicion_score"] <= 1.0
    features = analysis["features"]
    assert features["total_moves"] >= 20
    assert features["engine_match_rate_top1"] <= 1.0

    game_id = payload["game_id"]
    # Fetch report to ensure persistence works.
    report_response = client.get(f"/games/{game_id}/report")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["game_id"] == game_id
    assert "suspicion_score" in report
    assert report["summary"].startswith("Suspicion score")


def test_profile_ingest_and_report_flow() -> None:
    game_response = client.post(
        "/games/ingest",
        json={
            "source": "upload",
            "pgn": SAMPLE_PGN,
            "player_id": "profile-player",
            "move_timings": [{"ply": 1, "time_seconds": 4.2}, {"ply": 2, "time_seconds": 3.8}],
        },
    )
    game_id = game_response.json()["game_id"]

    profile_payload = {
        "profile_id": "profile-player",
        "platform": "lichess",
        "join_date": date(2020, 1, 1).isoformat(),
        "last_active": date(2024, 1, 1).isoformat(),
        "total_games": 420,
        "ratings": {"rapid": 2100, "blitz": 2050},
        "recent_games": [{"game_id": game_id, "result": "1-0", "rated": True}],
        "metadata": {"estimated_active_days": 600},
    }
    profile_response = client.post("/profiles/ingest", json=profile_payload)
    assert profile_response.status_code == 200, profile_response.text
    analytics = profile_response.json()
    assert analytics["profile_id"] == "profile-player"
    assert 0.0 <= analytics["risk_score"] <= 1.0
    assert analytics["game_count"] >= 1

    report_response = client.get("/profiles/profile-player/report")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["analytics"]["profile_id"] == "profile-player"
    assert "Risk score" in report["summary"]


def test_dataset_and_moderation_endpoints() -> None:
    dataset_response = client.post(
        "/datasets",
        json={
            "name": "Engine Pure Corpus",
            "kind": "engine_pure",
            "storage_uri": "s3://datasets/engine-pure",
            "record_count": 1000,
            "metadata": {"source": "tcec"},
        },
    )
    assert dataset_response.status_code == 200
    descriptor = dataset_response.json()
    dataset_id = UUID(descriptor["dataset_id"])  # ensure valid UUID

    training_response = client.post(
        "/models/cheetah/train",
        json={"dataset_ids": [str(dataset_id)], "hyperparameters": {"lr": 0.01}},
    )
    assert training_response.status_code == 200
    job = training_response.json()
    assert job["status"] == "queued"

    label_response = client.post(
        "/moderation/labels",
        json={
            "target_id": "profile-player",
            "target_type": "profile",
            "label": "engine_assist",
            "confidence": 0.85,
            "notes": "Strong evidence from latest review",
        },
    )
    assert label_response.status_code == 200
    label = label_response.json()
    assert label["label"] == "engine_assist"
    assert label["flags"]

    queue_response = client.post(
        "/moderation/queue",
        json={
            "target_id": "profile-player",
            "target_type": "profile",
            "reason": "Manual verification",
            "priority": "high",
        },
    )
    assert queue_response.status_code == 200
    queue_item = queue_response.json()
    assert queue_item["priority"] == "high"

    queue_list_response = client.get("/moderation/queue")
    assert queue_list_response.status_code == 200
    queue_items = queue_list_response.json()
    assert any(item["target_id"] == "profile-player" for item in queue_items)


def test_experiment_and_public_endpoints() -> None:
    session_response = client.post(
        "/experiment/session",
        json={"player_id": "volunteer-1", "mode": "assisted_20", "consent": True},
    )
    assert session_response.status_code == 200
    session = session_response.json()
    session_id = session["session_id"]

    completion_response = client.post(
        f"/experiment/session/{session_id}/complete",
        json={
            "pgn": "1. d4 d5 2. c4 e6 1/2-1/2",
            "move_labels": [{"ply": 1, "label": "human_clean", "confidence": 0.9}],
        },
    )
    assert completion_response.status_code == 200
    export = completion_response.json()
    assert export["session_id"] == session_id

    public_response = client.post("/analyze/url", json={"url": "https://lichess.org/game123"})
    assert public_response.status_code == 200
    ticket = public_response.json()
    assert ticket["status"] == "queued"
    assert ticket["reference_id"]


import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import jwt
from fastapi.testclient import TestClient

os.environ.setdefault("SERVER_JWT_SECRET", "test-secret")
os.environ.setdefault("SERVER_DATABASE_URL", "sqlite:///./test_server.db")

from server.app import app  # noqa: E402
from server.database import Base, engine  # noqa: E402

TEST_DB = Path("test_server.db")
if TEST_DB.exists():
    TEST_DB.unlink()

Base.metadata.create_all(bind=engine)
client = TestClient(app)

TOKEN = jwt.encode({"sub": "1"}, "test-secret", algorithm="HS256")


def auth_headers(token: str = TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_profile_lifecycle():
    update_response = client.put(
        "/profile",
        json={"display_name": "Test", "bio": "Test Bio", "rating": 1500},
        headers=auth_headers(),
    )
    assert update_response.status_code == 200, update_response.text
    profile = update_response.json()
    assert profile["display_name"] == "Test"
    assert profile["rating"] == 1500

    get_response = client.get("/profile", headers=auth_headers())
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["display_name"] == "Test"


def test_game_creation_and_listing():
    create_response = client.post(
        "/games",
        json={"opponent": "Opponent", "result": "win", "moves": "e4 e5"},
        headers=auth_headers(),
    )
    assert create_response.status_code == 201, create_response.text

    list_response = client.get("/games", headers=auth_headers())
    assert list_response.status_code == 200
    games = list_response.json()
    assert len(games) >= 1


def test_requires_authentication():
    response = client.get("/games")
    assert response.status_code == 401

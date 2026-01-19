import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("AUTH_JWT_SECRET", "test-secret")
os.environ.setdefault("AUTH_DATABASE_URL", "sqlite:///./test_auth.db")

from fastapi.testclient import TestClient

from auth.app import app
from auth.database import Base, engine


# Ensure the database is clean before running tests
if Path("test_auth.db").exists():
    Path("test_auth.db").unlink()

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def test_register_and_login():
    response = client.post(
        "/register",
        json={"email": "user@example.com", "password": "verysecurepassword", "full_name": "Test User"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["email"] == "user@example.com"

    login_response = client.post(
        "/login",
        json={"email": "user@example.com", "password": "verysecurepassword"},
    )
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]
    assert token


def test_duplicate_registration_is_prevented():
    response = client.post(
        "/register",
        json={"email": "dupe@example.com", "password": "anothersecurepass", "full_name": "Dupe"},
    )
    assert response.status_code == 201

    duplicate = client.post(
        "/register",
        json={"email": "dupe@example.com", "password": "anothersecurepass", "full_name": "Dupe"},
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "Email already registered"

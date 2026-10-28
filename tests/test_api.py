
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == (
        "Academic Integrity Case Management System API"
    )
    assert "environment" in data


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_me_without_token():
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_auth_me_with_invalid_token():
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid-test-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired access token"
    )


def test_login_with_unknown_username():
    response = client.post(
        "/auth/login",
        json={
            "username": "pytest_unknown_user_987654",
            "password": "invalid-test-password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid username or password"
    )


def test_login_rejects_missing_fields():
    response = client.post(
        "/auth/login",
        json={"username": "pytest_unknown_user_987654"},
    )

    assert response.status_code == 422

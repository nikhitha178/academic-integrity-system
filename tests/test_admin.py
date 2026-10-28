from types import SimpleNamespace
from datetime import datetime
from unittest.mock import MagicMock

from backend.app.database import get_db
from backend.app.models import AuditEvent

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api.auth import get_current_user


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


def make_user(role, username="test_user"):
    return SimpleNamespace(
        username=username,
        role=role,
        user_id="TEST-USER",
        is_active=True,
    )


def test_academic_administrator_can_access_admin_endpoint():
    user = make_user("Academic Administrator", "admin_test_user")
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.get("/admin/test")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Administrator access granted",
        "username": "admin_test_user",
        "role": "Academic Administrator",
    }


@pytest.mark.parametrize(
    "role",
    [
        "Platform Administrator",
        "Case Reviewer",
        "Learner",
        "Instructor",
        "Support Staff",
        "Independent Appeal Reviewer",
    ],
)
def test_non_academic_administrator_cannot_access_admin_endpoint(role):
    user = make_user(role)
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.get("/admin/test")

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "You do not have permission to perform this action."
    )


def test_admin_endpoint_requires_authentication():
    response = client.get("/admin/test")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def make_account(user_id="USR-TEST-002", is_active=True):
    return SimpleNamespace(
        user_id=user_id,
        username="test_account",
        email="test_account@academic.edu",
        role="Learner",
        is_active=is_active,
        created_at=datetime(2026, 1, 1),
    )


def configure_status_test(account):
    db = MagicMock()
    db.get.return_value = account
    app.dependency_overrides[get_db] = lambda: db
    admin = make_user("Academic Administrator", "admin_test_user")
    app.dependency_overrides[get_current_user] = lambda: admin
    return db, admin


def test_admin_can_deactivate_user_and_audit_change():
    account = make_account(is_active=True)
    db, admin = configure_status_test(account)

    response = client.patch(
        f"/admin/users/{account.user_id}/status",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["user"]["is_active"] is False
    assert account.is_active is False
    db.commit.assert_called_once()

    audit = next(
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], AuditEvent)
    )
    assert audit.actor_id == admin.user_id
    assert audit.event_type == "USER_STATUS_CHANGED"
    assert audit.entity_id == account.user_id


def test_admin_can_reactivate_user():
    account = make_account(is_active=False)
    db, _ = configure_status_test(account)

    response = client.patch(
        f"/admin/users/{account.user_id}/status",
        json={"is_active": True},
    )

    assert response.status_code == 200
    assert response.json()["user"]["is_active"] is True
    db.commit.assert_called_once()


def test_status_update_returns_404_for_missing_user():
    db, _ = configure_status_test(None)

    response = client.patch(
        "/admin/users/UNKNOWN-USER/status",
        json={"is_active": False},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found."
    db.commit.assert_not_called()


def test_admin_cannot_deactivate_own_account():
    admin = make_user("Academic Administrator", "admin_test_user")
    db = MagicMock()
    db.get.return_value = admin
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin

    response = client.patch(
        f"/admin/users/{admin.user_id}/status",
        json={"is_active": False},
    )

    assert response.status_code == 400
    db.commit.assert_not_called()


def test_status_update_requires_academic_administrator():
    account = make_account()
    db = MagicMock()
    db.get.return_value = account
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = (
        lambda: make_user("Case Reviewer")
    )

    response = client.patch(
        f"/admin/users/{account.user_id}/status",
        json={"is_active": False},
    )

    assert response.status_code == 403
    db.commit.assert_not_called()


def test_unchanged_status_does_not_create_audit_event():
    account = make_account(is_active=True)
    db, _ = configure_status_test(account)

    response = client.patch(
        f"/admin/users/{account.user_id}/status",
        json={"is_active": True},
    )

    assert response.status_code == 200
    db.commit.assert_not_called()
    db.add.assert_not_called()


def test_status_update_rolls_back_when_database_commit_fails():
    account = make_account(is_active=True)
    db, _ = configure_status_test(account)
    db.commit.side_effect = RuntimeError("Simulated database failure")

    with pytest.raises(RuntimeError, match="Simulated database failure"):
        client.patch(
            f"/admin/users/{account.user_id}/status",
            json={"is_active": False},
        )

    db.rollback.assert_called_once()


def test_admin_can_change_user_role_and_audit_change():
    account = make_account()
    db, admin = configure_status_test(account)

    response = client.patch(
        f"/admin/users/{account.user_id}/role",
        json={"role": "Instructor"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "Instructor"
    assert account.role == "Instructor"

    audit_event = next(
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], AuditEvent)
    )
    assert audit_event.event_type == "USER_ROLE_CHANGED"
    assert audit_event.entity_id == account.user_id
    assert audit_event.event_payload_json == {
        "old_role": "Learner",
        "new_role": "Instructor",
    }


def test_role_update_returns_404_for_missing_user():
    db, admin = configure_status_test(make_account())
    db.get.return_value = None

    response = client.patch(
        "/admin/users/USR-DOES-NOT-EXIST/role",
        json={"role": "Instructor"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found."
    db.commit.assert_not_called()


def test_admin_cannot_change_own_role():
    db, admin = configure_status_test(make_account())
    db.get.return_value = admin

    response = client.patch(
        f"/admin/users/{admin.user_id}/role",
        json={"role": "Platform Administrator"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot change your own role."
    db.commit.assert_not_called()


def test_role_update_requires_academic_administrator():
    account = make_account()
    db, admin = configure_status_test(account)

    from backend.app.api.auth import get_current_user

    learner = make_user("Learner", "learner_test_user")
    app.dependency_overrides[get_current_user] = lambda: learner

    response = client.patch(
        f"/admin/users/{account.user_id}/role",
        json={"role": "Instructor"},
    )

    assert response.status_code == 403
    db.commit.assert_not_called()


def test_role_update_rejects_invalid_role():
    account = make_account()
    db, admin = configure_status_test(account)

    response = client.patch(
        f"/admin/users/{account.user_id}/role",
        json={"role": "Super Administrator"},
    )

    assert response.status_code == 422
    db.commit.assert_not_called()


def test_unchanged_role_does_not_create_audit_event():
    account = make_account()
    db, admin = configure_status_test(account)

    response = client.patch(
        f"/admin/users/{account.user_id}/role",
        json={"role": "Learner"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "Learner"
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_role_update_rolls_back_when_database_commit_fails():
    account = make_account()
    db, admin = configure_status_test(account)
    db.commit.side_effect = RuntimeError("Simulated database failure")

    with pytest.raises(RuntimeError, match="Simulated database failure"):
        client.patch(
            f"/admin/users/{account.user_id}/role",
            json={"role": "Instructor"},
        )

    db.rollback.assert_called_once()


def test_admin_can_change_user_to_independent_appeal_reviewer():
    account = make_account()
    db, admin = configure_status_test(account)

    response = client.patch(
        f"/admin/users/{account.user_id}/role",
        json={"role": "Independent Appeal Reviewer"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == (
        "Independent Appeal Reviewer"
    )

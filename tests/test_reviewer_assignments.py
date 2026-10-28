from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.app.api.auth import get_current_user
from backend.app.database import get_db
from backend.app.main import app
from backend.app.models import AuditEvent, ReviewerAssignment
from fastapi.testclient import TestClient


client = TestClient(app)
_DEFAULT = object()


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    original = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original)


def make_user(
    user_id="ADMIN-TEST",
    role="Academic Administrator",
    is_active=True,
):
    return SimpleNamespace(
        user_id=user_id,
        username="test_user",
        email="test@example.com",
        role=role,
        is_active=is_active,
    )


def make_case(status="UNDER_INVESTIGATION"):
    return SimpleNamespace(
        case_id="CAS-TEST-001",
        case_status=status,
    )


def make_reviewer():
    return SimpleNamespace(
        reviewer_id="REV-TEST-001",
        user_id="REVIEWER-USER-001",
    )


def make_assignment(
    reviewer_id="REV-TEST-001",
    is_active=True,
):
    return SimpleNamespace(
        assignment_id="ASSIGNMENT-OLD",
        case_id="CAS-TEST-001",
        reviewer_id=reviewer_id,
        assigned_by_user_id="ADMIN-OLD",
        assignment_role="PRIMARY_INVESTIGATOR",
        assigned_at=datetime(2026, 1, 1),
        is_active=is_active,
    )


def setup_test(
    case=_DEFAULT,
    reviewer=_DEFAULT,
    reviewer_user=None,
    active_assignments=None,
    admin=None,
):
    db = MagicMock()
    case = make_case() if case is _DEFAULT else case
    reviewer = make_reviewer() if reviewer is _DEFAULT else reviewer
    reviewer_user = (
        reviewer_user
        if reviewer_user is not None
        else make_user(
            user_id="REVIEWER-USER-001",
            role="Case Reviewer",
        )
    )
    admin = admin if admin is not None else make_user()

    def get_record(model, record_id):
        from backend.app.models import Case, Reviewer, User

        if model is Case:
            return case
        if model is Reviewer:
            return reviewer
        if model is User:
            if record_id == "REVIEWER-USER-001":
                return reviewer_user
            if record_id == admin.user_id:
                return admin
        return None

    db.get.side_effect = get_record
    db.scalars.return_value.all.return_value = (
        active_assignments if active_assignments is not None else []
    )

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin

    return db, admin


def assign(reviewer_id="REV-TEST-001", case_id="CAS-TEST-001"):
    return client.post(
        f"/admin/cases/{case_id}/reviewer-assignment",
        json={"reviewer_id": reviewer_id},
    )


def test_admin_can_assign_reviewer_and_audit_change():
    db, admin = setup_test()

    response = assign()

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Reviewer assigned successfully."
    assert body["assignment"]["case_id"] == "CAS-TEST-001"
    assert body["assignment"]["reviewer_id"] == "REV-TEST-001"
    assert body["assignment"]["assignment_role"] == "PRIMARY_INVESTIGATOR"
    assert body["assignment"]["is_active"] is True
    db.commit.assert_called_once()

    audit = next(
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], AuditEvent)
    )
    assert audit.actor_id == admin.user_id
    assert audit.event_type == "REVIEWER_ASSIGNMENT_CHANGED"
    assert audit.entity_id == "CAS-TEST-001"


def test_reassignment_deactivates_old_assignment_and_preserves_history():
    old = make_assignment()
    new_reviewer = SimpleNamespace(
        reviewer_id="REV-TEST-002",
        user_id="REVIEWER-USER-001",
    )
    db, admin = setup_test(
        reviewer=new_reviewer,
        active_assignments=[old],
    )

    response = assign("REV-TEST-002")

    assert response.status_code == 200
    assert old.is_active is False

    # Historical assignments must be retained, never deleted.
    db.delete.assert_not_called()

    # The reassignment is committed once.
    db.commit.assert_called_once()

    new_assignment = next(
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], ReviewerAssignment)
    )

    assert new_assignment.case_id == "CAS-TEST-001"
    assert new_assignment.reviewer_id == "REV-TEST-002"
    assert new_assignment.assigned_by_user_id == admin.user_id
    assert new_assignment.assignment_role == "PRIMARY_INVESTIGATOR"
    assert new_assignment.is_active is True

    # The audit record must document both sides of the reassignment.
    audit = next(
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], AuditEvent)
    )

    assert audit.actor_id == admin.user_id
    assert audit.event_type == "REVIEWER_ASSIGNMENT_CHANGED"
    assert audit.entity_type == "Case"
    assert audit.entity_id == "CAS-TEST-001"
    assert audit.event_payload_json["previous_assignments"] == [
        {
            "assignment_id": old.assignment_id,
            "reviewer_id": "REV-TEST-001",
        }
    ]
    assert audit.event_payload_json["new_assignment_id"] == (
        new_assignment.assignment_id
    )
    assert audit.event_payload_json["new_reviewer_id"] == "REV-TEST-002"


def test_same_active_reviewer_does_not_create_duplicate():
    existing = make_assignment()
    db, _ = setup_test(active_assignments=[existing])

    response = assign()

    assert response.status_code == 200
    assert "already assigned" in response.json()["message"]
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_assignment_returns_404_for_missing_case():
    db, _ = setup_test(case=None)

    response = assign()

    assert response.status_code == 404
    assert response.json()["detail"] == "Case not found."
    db.commit.assert_not_called()


def test_assignment_rejects_case_not_under_investigation():
    db, _ = setup_test(case=make_case("DECIDED"))

    response = assign()

    assert response.status_code == 409
    db.commit.assert_not_called()


def test_assignment_returns_404_for_missing_reviewer():
    db, _ = setup_test(reviewer=None)

    response = assign()

    assert response.status_code == 404
    assert response.json()["detail"] == "Reviewer not found."
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "active,role",
    [
        (False, "Case Reviewer"),
        (True, "Learner"),
        (True, "Instructor"),
    ],
)
def test_assignment_rejects_inactive_or_wrong_role_user(active, role):
    reviewer_user = make_user(
        user_id="REVIEWER-USER-001",
        role=role,
        is_active=active,
    )
    db, _ = setup_test(reviewer_user=reviewer_user)

    response = assign()

    assert response.status_code == 422
    db.commit.assert_not_called()


def test_non_admin_cannot_assign_reviewer():
    admin = make_user(role="Case Reviewer")
    db, _ = setup_test(admin=admin)

    response = assign()

    assert response.status_code == 403
    db.commit.assert_not_called()


def test_assignment_rolls_back_when_commit_fails():
    db, _ = setup_test()
    db.commit.side_effect = RuntimeError("Simulated database failure")

    with pytest.raises(RuntimeError, match="Simulated database failure"):
        assign()

    db.rollback.assert_called_once()

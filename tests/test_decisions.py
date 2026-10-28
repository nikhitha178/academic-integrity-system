from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.api.auth import get_current_user
from backend.app.database import get_db
from backend.app.main import app
from backend.app.models import AuditEvent, Decision


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    original = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original)


def setup_decision_test(
    case_status="UNDER_INVESTIGATION",
    assignment="ASSIGNMENT-TEST",
    existing_decision=None,
):
    db = MagicMock()

    case = SimpleNamespace(
        case_id="CAS-TEST-001",
        case_status=case_status,
        updated_at=None,
    )

    reviewer = SimpleNamespace(
        reviewer_id="REV-TEST-001",
        user_id="USER-REVIEWER-001",
    )

    user = SimpleNamespace(
        user_id="USER-REVIEWER-001",
        username="reviewer_test",
        email="reviewer@example.com",
        role="Case Reviewer",
        is_active=True,
    )

    db.scalar.side_effect = [
        case,
        reviewer,
        assignment,
        existing_decision,
    ]

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user

    return db, case, user


def submit_decision():
    return client.post(
        "/cases/CAS-TEST-001/decision",
        json={
            "finding": "ACADEMIC_MISCONDUCT_FOUND",
            "sanction_recommended": "Formal warning",
            "rationale_text": (
                "The reviewed evidence supports this finding."
            ),
        },
    )


def test_assigned_reviewer_can_submit_decision_and_audit_event():
    db, case, user = setup_decision_test()

    response = submit_decision()

    assert response.status_code == 201
    body = response.json()

    assert body["case_id"] == "CAS-TEST-001"
    assert body["decision_maker_id"] == "REV-TEST-001"
    assert body["finding"] == "ACADEMIC_MISCONDUCT_FOUND"
    assert body["sanction_recommended"] == "Formal warning"

    assert case.case_status == "DECIDED"
    assert case.updated_at is not None
    db.commit.assert_called_once()
    db.refresh.assert_called_once()

    added_objects = db.add_all.call_args.args[0]
    decision = next(
        item for item in added_objects
        if isinstance(item, Decision)
    )
    audit = next(
        item for item in added_objects
        if isinstance(item, AuditEvent)
    )

    assert decision.case_id == "CAS-TEST-001"
    assert audit.actor_id == user.user_id
    assert audit.event_type == "CASE_DECISION_CREATED"
    assert audit.entity_type == "Decision"
    assert audit.entity_id == decision.decision_id


def test_unassigned_reviewer_cannot_submit_decision():
    db, case, _ = setup_decision_test(assignment=None)

    response = submit_decision()

    assert response.status_code == 403
    assert case.case_status == "UNDER_INVESTIGATION"
    db.add_all.assert_not_called()
    db.commit.assert_not_called()


def test_decision_rejected_when_case_is_not_under_investigation():
    db, case, _ = setup_decision_test(
        case_status="CLOSED",
    )

    response = submit_decision()

    assert response.status_code == 409
    assert case.case_status == "CLOSED"
    db.add_all.assert_not_called()
    db.commit.assert_not_called()


def test_duplicate_decision_is_rejected():
    db, case, _ = setup_decision_test(
        existing_decision="EXISTING-DECISION",
    )

    response = submit_decision()

    assert response.status_code == 409
    assert case.case_status == "UNDER_INVESTIGATION"
    db.add_all.assert_not_called()
    db.commit.assert_not_called()

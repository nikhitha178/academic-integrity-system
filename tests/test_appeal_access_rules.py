from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.app.api.appeals import get_accessible_appeal


def make_user(role, user_id="TEST-USER"):
    return SimpleNamespace(user_id=user_id, role=role)


def make_appeal():
    return SimpleNamespace(
        appeal_id="APL-TEST",
        case_id="CAS-TEST",
        independent_reviewer_id="REV-IND-TEST",
    )


def test_administrator_can_access_appeal():
    appeal = make_appeal()
    db = MagicMock()
    db.scalar.return_value = appeal

    result = get_accessible_appeal(
        "APL-TEST", make_user("Academic Administrator"), db
    )

    assert result is appeal


def test_platform_administrator_can_access_appeal():
    appeal = make_appeal()
    db = MagicMock()
    db.scalar.return_value = appeal

    result = get_accessible_appeal(
        "APL-TEST", make_user("Platform Administrator"), db
    )

    assert result is appeal


def test_missing_appeal_returns_404():
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        get_accessible_appeal(
            "APL-MISSING", make_user("Academic Administrator"), db
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Appeal not found."


def test_unassigned_learner_is_denied():
    appeal = make_appeal()
    db = MagicMock()
    db.scalar.side_effect = [appeal, None]

    with pytest.raises(HTTPException) as exc_info:
        get_accessible_appeal(
            "APL-TEST", make_user("Learner", "OTHER-LEARNER"), db
        )

    assert exc_info.value.status_code == 403


def test_unassigned_independent_reviewer_is_denied():
    appeal = make_appeal()
    db = MagicMock()
    db.scalar.side_effect = [appeal, None]

    with pytest.raises(HTTPException) as exc_info:
        get_accessible_appeal(
            "APL-TEST",
            make_user("Independent Appeal Reviewer", "OTHER-REVIEWER"),
            db,
        )

    assert exc_info.value.status_code == 403


def test_unsupported_role_is_denied():
    appeal = make_appeal()
    db = MagicMock()
    db.scalar.return_value = appeal

    with pytest.raises(HTTPException) as exc_info:
        get_accessible_appeal(
            "APL-TEST", make_user("Support Staff"), db
        )

    assert exc_info.value.status_code == 403


def test_case_owning_learner_can_access_appeal():
    appeal = make_appeal()
    db = MagicMock()

    # First query finds the appeal; second confirms ownership.
    db.scalar.side_effect = [appeal, "LEARNER-001"]

    result = get_accessible_appeal(
        "APL-TEST",
        make_user("Learner", "USER-LEARNER-001"),
        db,
    )

    assert result is appeal
    assert db.scalar.call_count == 2


def test_assigned_independent_reviewer_can_access_appeal():
    appeal = make_appeal()
    db = MagicMock()

    # First query finds the appeal; second confirms reviewer assignment.
    db.scalar.side_effect = [appeal, "REV-IND-TEST"]

    result = get_accessible_appeal(
        "APL-TEST",
        make_user(
            "Independent Appeal Reviewer",
            "USER-REVIEWER-001",
        ),
        db,
    )

    assert result is appeal
    assert db.scalar.call_count == 2

from types import SimpleNamespace
from unittest.mock import MagicMock, call

import hashlib
import json

import pytest
from fastapi import HTTPException
from fastapi import status
from pydantic import ValidationError
from datetime import datetime, timezone
from unittest.mock import patch

from backend.app.models import AuditEvent, Evidence
from backend.app.api.evidence import can_add_evidence, get_accessible_case, add_case_evidence
from backend.app.schemas.evidence import EvidenceCreate


def make_user(role, user_id="TEST-USER"):
    return SimpleNamespace(user_id=user_id, role=role)


def make_case(case_id="CAS-TEST", case_status="UNDER_INVESTIGATION"):
    return SimpleNamespace(case_id=case_id, case_status=case_status)


def test_evidence_type_cannot_be_empty():
    with pytest.raises(ValidationError):
        EvidenceCreate(evidence_type="", content_summary="Valid summary")


def test_evidence_summary_cannot_be_empty():
    with pytest.raises(ValidationError):
        EvidenceCreate(evidence_type="Document", content_summary="")


def test_evidence_type_maximum_length_is_80():
    with pytest.raises(ValidationError):
        EvidenceCreate(evidence_type="X" * 81, content_summary="Valid summary")


def test_evidence_summary_maximum_length_is_10000():
    with pytest.raises(ValidationError):
        EvidenceCreate(evidence_type="Document", content_summary="X" * 10001)


@pytest.mark.parametrize(
    "role",
    ["Academic Administrator", "Platform Administrator"],
)
def test_administrators_can_add_evidence(role):
    db = MagicMock()

    assert can_add_evidence("CAS-TEST", make_user(role), db) is True
    db.scalar.assert_not_called()


def test_non_reviewer_non_admin_cannot_add_evidence():
    db = MagicMock()

    assert can_add_evidence(
        "CAS-TEST", make_user("Learner"), db
    ) is False

    db.scalar.assert_not_called()


def test_reviewer_with_active_assignment_can_add_evidence():
    db = MagicMock()
    db.scalar.return_value = "ASSIGNMENT-001"

    result = can_add_evidence(
        "CAS-TEST", make_user("Case Reviewer", "USER-REVIEWER"), db
    )

    assert result is True
    db.scalar.assert_called_once()


def test_reviewer_without_active_assignment_cannot_add_evidence():
    db = MagicMock()
    db.scalar.return_value = None

    result = can_add_evidence(
        "CAS-TEST", make_user("Case Reviewer", "USER-REVIEWER"), db
    )

    assert result is False
    db.scalar.assert_called_once()


def test_inaccessible_case_returns_404():
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        get_accessible_case(
            "CAS-MISSING", make_user("Academic Administrator"), db
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "Case not found."


def test_evidence_checksum_uses_sha256():
    payload = {
        "case_id": "CAS-TEST",
        "evidence_id": "EVIDENCE-TEST",
        "evidence_type": "Document",
        "content_summary": "Example evidence",
        "added_by_user_id": "USER-TEST",
        "added_at": "2026-01-01T00:00:00+00:00",
        "version": 1,
    }

    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    checksum = hashlib.sha256(
        canonical_payload.encode("utf-8")
    ).hexdigest()

    assert len(checksum) == 64
    assert checksum == hashlib.sha256(
        canonical_payload.encode("utf-8")
    ).hexdigest()


def test_evidence_rejected_when_case_is_not_under_investigation():
    user = make_user("Academic Administrator")
    case = make_case(case_status="DECIDED")
    db = MagicMock()

    with patch(
        "backend.app.api.evidence.get_accessible_case",
        return_value=case,
    ):
        with pytest.raises(HTTPException) as exc_info:
            add_case_evidence(
                case_id="CAS-TEST",
                request=EvidenceCreate(
                    evidence_type="Document",
                    content_summary="Test evidence summary",
                ),
                current_user=user,
                db=db,
            )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_unauthorized_user_cannot_add_evidence():
    user = make_user("Learner")
    case = make_case()
    db = MagicMock()

    with patch(
        "backend.app.api.evidence.get_accessible_case",
        return_value=case,
    ):
        with pytest.raises(HTTPException) as exc_info:
            add_case_evidence(
                case_id="CAS-TEST",
                request=EvidenceCreate(
                    evidence_type="Document",
                    content_summary="Test evidence summary",
                ),
                current_user=user,
                db=db,
            )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_successful_evidence_creation_adds_audit_event():
    user = make_user("Academic Administrator", "USER-ADMIN")
    case = make_case()
    db = MagicMock()
    db.added_objects = []

    def preserve_added_objects(obj):
        db.added_objects.append(obj)

    db.add.side_effect = preserve_added_objects

    with patch(
        "backend.app.api.evidence.get_accessible_case",
        return_value=case,
    ), patch(
        "backend.app.api.evidence.uuid4",
        side_effect=[
            SimpleNamespace(hex="EVIDENCE-TEST"),
            SimpleNamespace(hex="AUDIT-TEST"),
        ],
    ):
        result = add_case_evidence(
            case_id="CAS-TEST",
            request=EvidenceCreate(
                evidence_type=" Document ",
                content_summary=" Example evidence ",
            ),
            current_user=user,
            db=db,
        )

    evidence_records = [
        obj for obj in db.added_objects if isinstance(obj, Evidence)
    ]
    audit_records = [
        obj for obj in db.added_objects if isinstance(obj, AuditEvent)
    ]

    assert result.evidence_id == "EVIDENCE-TEST"
    assert result.evidence_type == "Document"
    assert result.content_summary == "Example evidence"
    assert len(result.metadata_checksum) == 64
    assert result.version == 1

    assert len(evidence_records) == 1
    assert len(audit_records) == 1
    assert audit_records[0].event_type == "EVIDENCE_ADDED"
    assert audit_records[0].entity_id == "EVIDENCE-TEST"

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(result)


def test_database_error_rolls_back_evidence_creation():
    user = make_user("Academic Administrator", "USER-ADMIN")
    case = make_case()
    db = MagicMock()
    db.commit.side_effect = RuntimeError("Simulated database failure")

    with patch(
        "backend.app.api.evidence.get_accessible_case",
        return_value=case,
    ):
        with pytest.raises(RuntimeError, match="Simulated database failure"):
            add_case_evidence(
                case_id="CAS-TEST",
                request=EvidenceCreate(
                    evidence_type="Document",
                    content_summary="Test evidence summary",
                ),
                current_user=user,
                db=db,
            )

    db.add.assert_called()
    db.rollback.assert_called_once()

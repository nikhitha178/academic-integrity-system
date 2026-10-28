import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import get_current_user
from backend.app.api.cases import apply_case_access
from backend.app.database import get_db
from backend.app.models import AuditEvent, Case, Evidence, User
from backend.app.schemas.evidence import EvidenceCreate, EvidenceResponse

router = APIRouter(prefix="/cases", tags=["Evidence Management"])


def get_accessible_case(
    case_id: str,
    user: User,
    db: Session,
) -> Case:
    query = apply_case_access(select(Case), user)
    case = db.scalar(query.where(Case.case_id == case_id).limit(1))

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found.",
        )

    return case


def can_add_evidence(case_id: str, user: User, db: Session) -> bool:
    if user.role in {"Academic Administrator", "Platform Administrator"}:
        return True

    if user.role != "Case Reviewer":
        return False

    from backend.app.models import Reviewer, ReviewerAssignment

    assignment = db.scalar(
        select(ReviewerAssignment.assignment_id)
        .join(Reviewer, Reviewer.reviewer_id == ReviewerAssignment.reviewer_id)
        .where(
            Reviewer.user_id == user.user_id,
            ReviewerAssignment.case_id == case_id,
            ReviewerAssignment.is_active.is_(True),
        )
        .limit(1)
    )
    return assignment is not None


@router.get("/{case_id}/evidence", response_model=list[EvidenceResponse])
def list_case_evidence(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_accessible_case(case_id, current_user, db)

    records = db.scalars(
        select(Evidence)
        .where(Evidence.case_id == case_id)
        .order_by(Evidence.added_at.asc(), Evidence.evidence_id.asc())
    ).all()

    return records


@router.post(
    "/{case_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_case_evidence(
    case_id: str,
    request: EvidenceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = get_accessible_case(case_id, current_user, db)

    if not can_add_evidence(case.case_id, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not permitted to add evidence to this case.",
        )

    if case.case_status != "UNDER_INVESTIGATION":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evidence can only be added while a case is under investigation.",
        )

    now = datetime.now(timezone.utc)
    evidence_id = uuid4().hex

    checksum_payload = {
        "case_id": case.case_id,
        "evidence_id": evidence_id,
        "evidence_type": request.evidence_type.strip(),
        "content_summary": request.content_summary.strip(),
        "added_by_user_id": current_user.user_id,
        "added_at": now.isoformat(),
        "version": 1,
    }
    canonical_payload = json.dumps(
        checksum_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    checksum = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

    evidence = Evidence(
        evidence_id=evidence_id,
        case_id=case.case_id,
        evidence_type=request.evidence_type.strip(),
        content_summary=request.content_summary.strip(),
        metadata_checksum=checksum,
        added_by_user_id=current_user.user_id,
        added_at=now,
        version=1,
    )

    audit_event = AuditEvent(
        event_id=uuid4().hex,
        actor_id=current_user.user_id,
        event_type="EVIDENCE_ADDED",
        entity_type="Evidence",
        entity_id=evidence_id,
        event_payload_json={
            "case_id": case.case_id,
            "evidence_type": request.evidence_type.strip(),
            "version": 1,
            "metadata_checksum": checksum,
        },
        timestamp=now,
    )

    try:
        db.add(evidence)
        db.add(audit_event)
        db.commit()
        db.refresh(evidence)
    except Exception:
        db.rollback()
        raise

    return evidence


import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.auth import get_current_user
from backend.app.database import get_db
from backend.app.models import (
    AuditEvent,
    Case,
    Decision,
    Reviewer,
    ReviewerAssignment,
    User,
)
from backend.app.schemas.decisions import DecisionCreate, DecisionResponse

router = APIRouter(prefix="/cases", tags=["Case Decisions"])


@router.post(
    "/{case_id}/decision",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_case_decision(
    case_id: str,
    request: DecisionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Find the case.
    case = db.scalar(
        select(Case).where(Case.case_id == case_id).with_for_update()
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")

    # Only a reviewer actively assigned to this case may decide it.
    reviewer = db.scalar(
        select(Reviewer).where(Reviewer.user_id == current_user.user_id)
    )
    if reviewer is None:
        raise HTTPException(
            status_code=403,
            detail="Your account is not registered as a reviewer.",
        )

    assignment = db.scalar(
        select(ReviewerAssignment.assignment_id).where(
            ReviewerAssignment.case_id == case_id,
            ReviewerAssignment.reviewer_id == reviewer.reviewer_id,
            ReviewerAssignment.is_active.is_(True),
        ).limit(1)
    )
    if assignment is None:
        raise HTTPException(
            status_code=403,
            detail="You are not actively assigned to this case.",
        )

    if case.case_status != "UNDER_INVESTIGATION":
        raise HTTPException(
            status_code=409,
            detail="A decision can only be submitted for a case under investigation.",
        )

    existing_decision = db.scalar(
        select(Decision.decision_id).where(Decision.case_id == case_id)
    )
    if existing_decision is not None:
        raise HTTPException(
            status_code=409,
            detail="A decision already exists for this case.",
        )

    now = datetime.now(timezone.utc)
    decision_id = uuid.uuid4().hex

    decision = Decision(
        decision_id=decision_id,
        case_id=case.case_id,
        decision_maker_id=reviewer.reviewer_id,
        finding=request.finding,
        sanction_recommended=request.sanction_recommended.strip(),
        rationale_text=request.rationale_text.strip(),
        decided_at=now,
    )

    case.case_status = "DECIDED"
    case.updated_at = now

    audit_event = AuditEvent(
        event_id=uuid.uuid4().hex,
        actor_id=current_user.user_id,
        event_type="CASE_DECISION_CREATED",
        entity_type="Decision",
        entity_id=decision_id,
        event_payload_json={
            "case_id": case.case_id,
            "finding": request.finding,
            "sanction_recommended": request.sanction_recommended.strip(),
        },
        timestamp=now,
    )

    try:
        db.add_all([decision, audit_event])
        db.commit()
        db.refresh(decision)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The decision conflicts with an existing record. Refresh the case and try again.",
        )
    except Exception:
        db.rollback()
        raise

    return decision

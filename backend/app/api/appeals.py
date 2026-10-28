
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.auth import get_current_user
from backend.app.database import get_db
from backend.app.models import (
    Appeal,
    AuditEvent,
    Case,
    Decision,
    Learner,
    Reviewer,
    Submission,
    User,
)
from backend.app.schemas.appeals import (
    AppealCreate,
    AppealResponse,
    AppealReviewCreate,
)

router = APIRouter(prefix="/appeals", tags=["Appeals Management"])

ADMIN_ROLES = {"Academic Administrator", "Platform Administrator"}


def get_accessible_appeal(
    appeal_id: str,
    user: User,
    db: Session,
) -> Appeal:
    appeal = db.scalar(
        select(Appeal).where(Appeal.appeal_id == appeal_id)
    )

    if appeal is None:
        raise HTTPException(status_code=404, detail="Appeal not found.")

    if user.role in ADMIN_ROLES:
        return appeal

    if user.role == "Learner":
        owns_case = db.scalar(
            select(Learner.learner_id)
            .join(
                Submission,
                Submission.learner_id == Learner.learner_id,
            )
            .join(Case, Case.submission_id == Submission.submission_id)
            .where(
                Case.case_id == appeal.case_id,
                Learner.user_id == user.user_id,
            )
            .limit(1)
        )
        if owns_case:
            return appeal

    elif user.role == "Independent Appeal Reviewer":
        assigned = db.scalar(
            select(Reviewer.reviewer_id)
            .where(
                Reviewer.reviewer_id == appeal.independent_reviewer_id,
                Reviewer.user_id == user.user_id,
            )
            .limit(1)
        )
        if assigned:
            return appeal

    raise HTTPException(
        status_code=403,
        detail="You do not have permission to access this appeal.",
    )


@router.post(
    "/{case_id}",
    response_model=AppealResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_appeal(
    case_id: str,
    request: AppealCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "Learner":
        raise HTTPException(
            status_code=403,
            detail="Only the learner associated with a case can submit an appeal.",
        )

    try:
        case = db.scalar(
            select(Case)
            .where(Case.case_id == case_id)
            .with_for_update()
        )

        if case is None:
            raise HTTPException(status_code=404, detail="Case not found.")

        owns_case = db.scalar(
            select(Learner.learner_id)
            .join(
                Submission,
                Submission.learner_id == Learner.learner_id,
            )
            .where(
                Submission.submission_id == case.submission_id,
                Learner.user_id == current_user.user_id,
            )
            .limit(1)
        )

        if owns_case is None:
            raise HTTPException(
                status_code=403,
                detail="You can only appeal your own case.",
            )

        if case.case_status != "DECIDED":
            raise HTTPException(
                status_code=409,
                detail="Only a decided case without an existing appeal is eligible.",
            )

        decision = db.scalar(
            select(Decision).where(Decision.case_id == case_id)
        )

        if decision is None:
            raise HTTPException(
                status_code=409,
                detail="A decision must exist before an appeal can be submitted.",
            )

        existing_appeal = db.scalar(
            select(Appeal.appeal_id)
            .where(Appeal.case_id == case_id)
            .limit(1)
        )

        if existing_appeal is not None:
            raise HTTPException(
                status_code=409,
                detail="An appeal already exists for this case.",
            )

        # Select an active independent reviewer other than
        # the reviewer who made the original decision.
        candidates = db.execute(
            select(Reviewer, User)
            .join(User, User.user_id == Reviewer.user_id)
            .where(
                User.role == "Independent Appeal Reviewer",
                User.is_active.is_(True),
                Reviewer.reviewer_id != decision.decision_maker_id,
            )
            .order_by(Reviewer.reviewer_id)
        ).all()

        if not candidates:
            raise HTTPException(
                status_code=503,
                detail="No eligible independent appeal reviewer is available.",
            )

        # Prefer the reviewer with the fewest appeals currently
        # under independent review.
        reviewer_loads = []
        for reviewer, reviewer_user in candidates:
            load = db.scalar(
                select(func.count())
                .select_from(Appeal)
                .where(
                    Appeal.independent_reviewer_id == reviewer.reviewer_id,
                    Appeal.appeal_status == "UNDER_INDEPENDENT_REVIEW",
                )
            ) or 0

            reviewer_loads.append(
                (load, reviewer.reviewer_id, reviewer, reviewer_user)
            )

        _, _, selected_reviewer, _ = min(
            reviewer_loads,
            key=lambda item: (item[0], item[1]),
        )

        now = datetime.now(timezone.utc)
        appeal_id = uuid.uuid4().hex

        appeal = Appeal(
            appeal_id=appeal_id,
            case_id=case.case_id,
            decision_id=decision.decision_id,
            independent_reviewer_id=selected_reviewer.reviewer_id,
            appeal_reason=request.appeal_reason.strip(),
            appeal_status="UNDER_INDEPENDENT_REVIEW",
            submitted_at=now,
            review_completed_at=None,
            review_outcome=None,
        )

        case.case_status = "APPEALED"
        case.updated_at = now

        audit_event = AuditEvent(
            event_id=uuid.uuid4().hex,
            actor_id=current_user.user_id,
            event_type="APPEAL_SUBMITTED",
            entity_type="Appeal",
            entity_id=appeal_id,
            event_payload_json={
                "case_id": case.case_id,
                "decision_id": decision.decision_id,
                "independent_reviewer_id": selected_reviewer.reviewer_id,
                "appeal_status": "UNDER_INDEPENDENT_REVIEW",
            },
            timestamp=now,
        )

        db.add_all([appeal, audit_event])
        db.commit()
        db.refresh(appeal)

        return appeal

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An appeal already exists or a record conflicts with this request.",
        )
    except Exception:
        db.rollback()
        raise


@router.get("", response_model=list[AppealResponse])
def list_appeals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Appeal)

    if current_user.role in ADMIN_ROLES:
        pass

    elif current_user.role == "Learner":
        query = (
            query.join(Case, Case.case_id == Appeal.case_id)
            .join(
                Submission,
                Submission.submission_id == Case.submission_id,
            )
            .join(
                Learner,
                Learner.learner_id == Submission.learner_id,
            )
            .where(Learner.user_id == current_user.user_id)
        )

    elif current_user.role == "Independent Appeal Reviewer":
        reviewer_id = db.scalar(
            select(Reviewer.reviewer_id).where(
                Reviewer.user_id == current_user.user_id
            )
        )

        if reviewer_id is None:
            return []

        query = query.where(
            Appeal.independent_reviewer_id == reviewer_id
        )

    else:
        raise HTTPException(
            status_code=403,
            detail="Your role cannot list appeals.",
        )

    return db.scalars(
        query.order_by(Appeal.submitted_at.desc())
    ).all()


@router.get("/{appeal_id}", response_model=AppealResponse)
def get_appeal(
    appeal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_accessible_appeal(appeal_id, current_user, db)


@router.post(
    "/{appeal_id}/review",
    response_model=AppealResponse,
)
def complete_appeal_review(
    appeal_id: str,
    request: AppealReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "Independent Appeal Reviewer":
        raise HTTPException(
            status_code=403,
            detail="Only an independent appeal reviewer can complete a review.",
        )

    reviewer = db.scalar(
        select(Reviewer).where(Reviewer.user_id == current_user.user_id)
    )

    if reviewer is None:
        raise HTTPException(
            status_code=403,
            detail="Your account is not registered as a reviewer.",
        )

    try:
        appeal = db.scalar(
            select(Appeal)
            .where(Appeal.appeal_id == appeal_id)
            .with_for_update()
        )

        if appeal is None:
            raise HTTPException(status_code=404, detail="Appeal not found.")

        if appeal.independent_reviewer_id != reviewer.reviewer_id:
            raise HTTPException(
                status_code=403,
                detail="You are not assigned to review this appeal.",
            )

        decision = db.scalar(
            select(Decision).where(
                Decision.decision_id == appeal.decision_id
            )
        )

        if decision is None:
            raise HTTPException(
                status_code=409,
                detail="The original decision could not be found.",
            )

        if decision.decision_maker_id == reviewer.reviewer_id:
            raise HTTPException(
                status_code=403,
                detail="The original decision-maker cannot review their own decision.",
            )

        if appeal.appeal_status != "UNDER_INDEPENDENT_REVIEW":
            raise HTTPException(
                status_code=409,
                detail="This appeal is not awaiting independent review.",
            )

        now = datetime.now(timezone.utc)

        appeal.review_outcome = request.review_outcome
        appeal.review_completed_at = now
        appeal.appeal_status = "CLOSED"

        case = db.scalar(
            select(Case)
            .where(Case.case_id == appeal.case_id)
            .with_for_update()
        )

        if case is None:
            raise HTTPException(
                status_code=409,
                detail="The case associated with this appeal could not be found.",
            )

        case.case_status = "CLOSED"
        case.updated_at = now

        audit_event = AuditEvent(
            event_id=uuid.uuid4().hex,
            actor_id=current_user.user_id,
            event_type="APPEAL_REVIEW_COMPLETED",
            entity_type="Appeal",
            entity_id=appeal.appeal_id,
            event_payload_json={
                "case_id": appeal.case_id,
                "review_outcome": request.review_outcome,
                "appeal_status": "CLOSED",
            },
            timestamp=now,
        )

        db.add(audit_event)
        db.commit()
        db.refresh(appeal)

        return appeal

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The review conflicts with an existing record.",
        )
    except Exception:
        db.rollback()
        raise

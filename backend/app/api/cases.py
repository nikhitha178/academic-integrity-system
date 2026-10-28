from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.auth import get_current_user
from backend.app.database import get_db
from backend.app.models import (
    Appeal,
    Assessment,
    Case,
    Instructor,
    Learner,
    Reviewer,
    ReviewerAssignment,
    Submission,
    User,
)
from backend.app.schemas.cases import CaseListResponse, CaseResponse

router = APIRouter(prefix="/cases", tags=["Case Management"])


def apply_case_access(query, user: User):
    """Restrict cases to administrators or users with a relevant relationship."""

    if user.role in {"Academic Administrator", "Platform Administrator"}:
        return query

    if user.role == "Case Reviewer":
        return (
            query.join(
                ReviewerAssignment,
                ReviewerAssignment.case_id == Case.case_id,
            )
            .join(
                Reviewer,
                Reviewer.reviewer_id == ReviewerAssignment.reviewer_id,
            )
            .where(
                Reviewer.user_id == user.user_id,
                ReviewerAssignment.is_active.is_(True),
            )
            .distinct()
        )

    if user.role == "Learner":
        return (
            query.join(Submission, Submission.submission_id == Case.submission_id)
            .join(Learner, Learner.learner_id == Submission.learner_id)
            .where(Learner.user_id == user.user_id)
        )

    if user.role == "Instructor":
        return (
            query.join(Submission, Submission.submission_id == Case.submission_id)
            .join(
                Assessment,
                Assessment.assessment_id == Submission.assessment_id,
            )
            .join(
                Instructor,
                Instructor.instructor_id
                == Assessment.created_by_instructor_id,
            )
            .where(Instructor.user_id == user.user_id)
        )

    if user.role == "Independent Appeal Reviewer":
        return (
            query.join(Appeal, Appeal.case_id == Case.case_id)
            .join(
                Reviewer,
                Reviewer.reviewer_id == Appeal.independent_reviewer_id,
            )
            .where(Reviewer.user_id == user.user_id)
        )

    raise HTTPException(
        status_code=403,
        detail="Your role does not have permission to view cases.",
    )


@router.get("", response_model=CaseListResponse)
def list_cases(
    status_filter: str | None = Query(
        default=None,
        alias="status",
        pattern="^(UNDER_INVESTIGATION|DECIDED|APPEALED|CLOSED)$",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base_query = select(Case)
    base_query = apply_case_access(base_query, current_user)

    if status_filter:
        base_query = base_query.where(Case.case_status == status_filter)

    total_query = select(func.count()).select_from(
        base_query.order_by(None).subquery()
    )
    total = db.scalar(total_query) or 0

    cases = db.scalars(
        base_query.order_by(Case.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return CaseListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[CaseResponse.model_validate(case) for case in cases],
    )


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = apply_case_access(select(Case), current_user)
    case = db.scalar(query.where(Case.case_id == case_id).limit(1))

    if case is None:
        # Avoid revealing whether an inaccessible case exists.
        raise HTTPException(status_code=404, detail="Case not found.")

    return CaseResponse.model_validate(case)

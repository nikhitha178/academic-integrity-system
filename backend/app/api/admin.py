
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from backend.app.models import AuditEvent
from backend.app.schemas.admin import (
    AdminActionResponse,
    UserRoleUpdate,
    UserStatusUpdate,
)
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.auth import get_current_user
from backend.app.database import get_db
from backend.app.models import User
from backend.app.schemas.admin import (
    AdminUserListResponse,
    AdminUserResponse,
)
from backend.app.services.permissions import require_roles

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/test")
def admin_test(
    current_user: User = Depends(
        require_roles("Academic Administrator")
    ),
):
    return {
        "message": "Administrator access granted",
        "username": current_user.username,
        "role": current_user.role,
    }


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    role: str | None = Query(default=None, min_length=1, max_length=60),
    current_user: User = Depends(
        require_roles("Academic Administrator")
    ),
    db: Session = Depends(get_db),
):
    query = select(User)

    if role is not None:
        query = query.where(User.role == role)

    total_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(total_query) or 0

    users = db.scalars(
        query
        .order_by(User.username.asc())
        .offset(offset)
        .limit(limit)
    ).all()

    return AdminUserListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            AdminUserResponse.model_validate(user)
            for user in users
        ],
    )


@router.patch("/users/{user_id}/status", response_model=AdminActionResponse)
def update_user_status(
    user_id: str,
    request: UserStatusUpdate,
    current_user: User = Depends(
        require_roles("Academic Administrator")
    ),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    if user_id == current_user.user_id and not request.is_active:
        raise HTTPException(
            status_code=400,
            detail="You cannot deactivate your own account.",
        )

    old_status = user.is_active
    new_status = request.is_active

    if old_status == new_status:
        return AdminActionResponse(
            message="User status is already set to the requested value.",
            user=user,
        )

    try:
        user.is_active = new_status

        audit_event = AuditEvent(
            event_id=uuid4().hex,
            actor_id=current_user.user_id,
            event_type="USER_STATUS_CHANGED",
            entity_type="User",
            entity_id=user.user_id,
            event_payload_json={
                "old_is_active": old_status,
                "new_is_active": new_status,
            },
            timestamp=datetime.now(timezone.utc),
        )

        db.add(audit_event)
        db.commit()
        db.refresh(user)

        return AdminActionResponse(
            message="User status updated successfully.",
            user=user,
        )

    except Exception:
        db.rollback()
        raise


@router.patch("/users/{user_id}/role", response_model=AdminActionResponse)
def update_user_role(
    user_id: str,
    request: UserRoleUpdate,
    current_user: User = Depends(
        require_roles("Academic Administrator")
    ),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=400,
            detail="You cannot change your own role.",
        )

    old_role = user.role
    new_role = request.role

    if old_role == new_role:
        return AdminActionResponse(
            message="User already has the requested role.",
            user=user,
        )

    try:
        user.role = new_role

        audit_event = AuditEvent(
            event_id=uuid4().hex,
            actor_id=current_user.user_id,
            event_type="USER_ROLE_CHANGED",
            entity_type="User",
            entity_id=user.user_id,
            event_payload_json={
                "old_role": old_role,
                "new_role": new_role,
            },
            timestamp=datetime.now(timezone.utc),
        )

        db.add(audit_event)
        db.commit()
        db.refresh(user)

        return AdminActionResponse(
            message="User role updated successfully.",
            user=user,
        )

    except Exception:
        db.rollback()
        raise


# Reviewer assignment management
from backend.app.models import Case, Reviewer, ReviewerAssignment
from backend.app.schemas.admin import (
    ReviewerAssignmentActionResponse,
    ReviewerAssignmentCreate,
    ReviewerAssignmentResponse,
)


@router.post(
    "/cases/{case_id}/reviewer-assignment",
    response_model=ReviewerAssignmentActionResponse,
)
def assign_case_reviewer(
    case_id: str,
    request: ReviewerAssignmentCreate,
    current_user: User = Depends(
        require_roles("Academic Administrator")
    ),
    db: Session = Depends(get_db),
):
    case = db.get(Case, case_id)

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    if case.case_status != "UNDER_INVESTIGATION":
        raise HTTPException(
            status_code=409,
            detail="A reviewer can only be assigned to a case under investigation.",
        )

    reviewer = db.get(Reviewer, request.reviewer_id)

    if reviewer is None:
        raise HTTPException(
            status_code=404,
            detail="Reviewer not found.",
        )

    reviewer_user = db.get(User, reviewer.user_id)

    if (
        reviewer_user is None
        or not reviewer_user.is_active
        or reviewer_user.role != "Case Reviewer"
    ):
        raise HTTPException(
            status_code=422,
            detail="The selected reviewer must have an active Case Reviewer account.",
        )

    active_assignments = db.scalars(
        select(ReviewerAssignment).where(
            ReviewerAssignment.case_id == case_id,
            ReviewerAssignment.is_active.is_(True),
        )
    ).all()

    # Avoid creating a duplicate when this is already the sole active assignment.
    if (
        len(active_assignments) == 1
        and active_assignments[0].reviewer_id == reviewer.reviewer_id
    ):
        existing = active_assignments[0]
        return ReviewerAssignmentActionResponse(
            message="This reviewer is already assigned to the case.",
            assignment=ReviewerAssignmentResponse(
                assignment_id=existing.assignment_id,
                case_id=existing.case_id,
                reviewer_id=existing.reviewer_id,
                assigned_by_user_id=existing.assigned_by_user_id,
                assignment_role=existing.assignment_role,
                assigned_at=existing.assigned_at,
                is_active=existing.is_active,
            ),
        )

    try:
        previous_assignments = [
            {
                "assignment_id": assignment.assignment_id,
                "reviewer_id": assignment.reviewer_id,
            }
            for assignment in active_assignments
        ]

        # Preserve assignment history: deactivate, never delete.
        for assignment in active_assignments:
            assignment.is_active = False

        now = datetime.now(timezone.utc)
        new_assignment = ReviewerAssignment(
            assignment_id=uuid4().hex,
            case_id=case_id,
            reviewer_id=reviewer.reviewer_id,
            assigned_by_user_id=current_user.user_id,
            assignment_role="PRIMARY_INVESTIGATOR",
            assigned_at=now,
            is_active=True,
        )

        audit_event = AuditEvent(
            event_id=uuid4().hex,
            actor_id=current_user.user_id,
            event_type="REVIEWER_ASSIGNMENT_CHANGED",
            entity_type="Case",
            entity_id=case_id,
            event_payload_json={
                "previous_assignments": previous_assignments,
                "new_assignment_id": new_assignment.assignment_id,
                "new_reviewer_id": reviewer.reviewer_id,
            },
            timestamp=now,
        )

        db.add(new_assignment)
        db.add(audit_event)
        db.commit()
        db.refresh(new_assignment)

        return ReviewerAssignmentActionResponse(
            message="Reviewer assigned successfully.",
            assignment=ReviewerAssignmentResponse(
                assignment_id=new_assignment.assignment_id,
                case_id=new_assignment.case_id,
                reviewer_id=new_assignment.reviewer_id,
                assigned_by_user_id=new_assignment.assigned_by_user_id,
                assignment_role=new_assignment.assignment_role,
                assigned_at=new_assignment.assigned_at,
                is_active=new_assignment.is_active,
            ),
        )

    except Exception:
        db.rollback()
        raise

# Reviewer directory and current assignment lookup (read-only endpoints)

@router.get("/reviewers")
def list_active_reviewers(
    current_user: User = Depends(
        require_roles("Academic Administrator")
    ),
    db: Session = Depends(get_db),
):
    """List reviewer profiles linked to active Case Reviewer accounts."""
    rows = db.execute(
        select(Reviewer, User)
        .join(User, Reviewer.user_id == User.user_id)
        .where(
            User.role == "Case Reviewer",
            User.is_active.is_(True),
        )
        .order_by(Reviewer.full_name.asc())
    ).all()

    return {
        "total": len(rows),
        "items": [
            {
                "reviewer_id": reviewer.reviewer_id,
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "full_name": reviewer.full_name,
                "department": reviewer.department,
                "specialization": reviewer.specialization,
            }
            for reviewer, user in rows
        ],
    }


@router.get("/cases/{case_id}/reviewer-assignment")
def get_case_reviewer_assignment(
    case_id: str,
    current_user: User = Depends(
        require_roles("Academic Administrator")
    ),
    db: Session = Depends(get_db),
):
    """Return the current active reviewer assignment for a case."""
    case = db.get(Case, case_id)

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    rows = db.execute(
        select(ReviewerAssignment, Reviewer, User)
        .join(
            Reviewer,
            ReviewerAssignment.reviewer_id == Reviewer.reviewer_id,
        )
        .join(User, Reviewer.user_id == User.user_id)
        .where(
            ReviewerAssignment.case_id == case_id,
            ReviewerAssignment.is_active.is_(True),
        )
        .order_by(ReviewerAssignment.assigned_at.desc())
    ).all()

    return {
        "case_id": case_id,
        "active_assignments": [
            {
                "assignment_id": assignment.assignment_id,
                "reviewer_id": reviewer.reviewer_id,
                "reviewer_name": reviewer.full_name,
                "reviewer_username": user.username,
                "assignment_role": assignment.assignment_role,
                "assigned_by_user_id": assignment.assigned_by_user_id,
                "assigned_at": assignment.assigned_at.isoformat(),
                "is_active": assignment.is_active,
            }
            for assignment, reviewer, user in rows
        ],
    }

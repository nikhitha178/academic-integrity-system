from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


UserRole = Literal[
    "Academic Administrator",
    "Platform Administrator",
    "Support Staff",
    "Learner",
    "Instructor",
    "Case Reviewer",
    "Independent Appeal Reviewer",
]


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


class AdminUserListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AdminUserResponse]


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserRoleUpdate(BaseModel):
    role: UserRole


class AdminActionResponse(BaseModel):
    message: str
    user: AdminUserResponse


class ReviewerAssignmentCreate(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=32)


class ReviewerAssignmentResponse(BaseModel):
    assignment_id: str
    case_id: str
    reviewer_id: str
    assigned_by_user_id: str
    assignment_role: str
    assigned_at: datetime
    is_active: bool


class ReviewerAssignmentActionResponse(BaseModel):
    message: str
    assignment: ReviewerAssignmentResponse

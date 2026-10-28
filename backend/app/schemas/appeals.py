
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AppealStatus = Literal[
    "UNDER_INDEPENDENT_REVIEW",
    "CLOSED",
]

AppealOutcome = Literal[
    "UPHELD",
    "OVERTURNED",
]


class AppealCreate(BaseModel):
    appeal_reason: str = Field(
        min_length=20,
        max_length=10000,
    )


class AppealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    appeal_id: str
    case_id: str
    decision_id: str
    independent_reviewer_id: str
    appeal_reason: str
    appeal_status: AppealStatus
    submitted_at: datetime
    review_completed_at: datetime | None
    review_outcome: AppealOutcome | None


class AppealReviewCreate(BaseModel):
    review_outcome: AppealOutcome

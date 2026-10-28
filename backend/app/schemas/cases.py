from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: str
    flag_id: str
    submission_id: str
    case_status: str
    created_at: datetime
    updated_at: datetime


class CaseListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[CaseResponse]

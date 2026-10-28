from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FindingType = Literal[
    "ACADEMIC_MISCONDUCT_FOUND",
    "NO_MISCONDUCT_FOUND",
    "INSUFFICIENT_EVIDENCE",
]


class DecisionCreate(BaseModel):
    finding: FindingType
    sanction_recommended: str = Field(min_length=1, max_length=80)
    rationale_text: str = Field(min_length=10, max_length=10000)


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_id: str
    case_id: str
    decision_maker_id: str
    finding: FindingType
    sanction_recommended: str
    rationale_text: str
    decided_at: datetime

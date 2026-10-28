from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvidenceCreate(BaseModel):
    evidence_type: str = Field(min_length=1, max_length=80)
    content_summary: str = Field(min_length=1, max_length=10000)


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_id: str
    case_id: str
    evidence_type: str
    content_summary: str
    metadata_checksum: str
    added_by_user_id: str
    added_at: datetime
    version: int

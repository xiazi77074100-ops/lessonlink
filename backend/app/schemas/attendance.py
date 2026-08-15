import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AttendanceStatus = Literal["ATTENDING", "ABSENT", "LATE", "NO_RESPONSE"]


class AttendanceUpsert(BaseModel):
    event_id: uuid.UUID
    child_id: uuid.UUID
    status: AttendanceStatus
    note: str | None = Field(default=None, max_length=500)


class AttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    child_id: uuid.UUID
    status: AttendanceStatus
    note: str | None
    responded_at: datetime | None


class AttendanceRowResponse(AttendanceResponse):
    child_first_name: str
    child_last_name: str


class AttendanceSummary(BaseModel):
    attending: int
    absent: int
    late: int
    no_response: int
    total: int


class EventAttendanceResponse(BaseModel):
    event_id: uuid.UUID
    summary: AttendanceSummary
    attendances: list[AttendanceRowResponse]

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.attendance import AttendanceStatus


class LineLoginRequest(BaseModel):
    id_token: str = Field(min_length=1)
    invitation_code: str = Field(min_length=1, max_length=32)


class ParentTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AvailableChildResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    grade: str | None


class BindChildRequest(BaseModel):
    child_id: uuid.UUID
    birth_date: date


class ParentChildSummary(AvailableChildResponse):
    pass


class ParentMeResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    display_name: str
    children: list[ParentChildSummary]


class ParentEventChildResponse(BaseModel):
    child_id: uuid.UUID
    child_name: str
    attendance_status: AttendanceStatus


class ParentEventResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    location_name: str | None
    location_address: str | None
    children: list[ParentEventChildResponse]


class ParentAttendanceRequest(BaseModel):
    event_id: uuid.UUID
    child_id: uuid.UUID
    status: AttendanceStatus

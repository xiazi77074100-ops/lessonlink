import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.child import ChildResponse


class ParentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    display_name: str
    email: EmailStr | None
    phone: str | None
    created_at: datetime
    updated_at: datetime


class ParentDetailResponse(ParentResponse):
    children: list[ChildResponse]


class ParentChildCreate(BaseModel):
    child_id: uuid.UUID

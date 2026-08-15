import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChildFields(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    first_name_kana: str | None = Field(default=None, max_length=50)
    last_name_kana: str | None = Field(default=None, max_length=50)
    birth_date: date
    grade: str | None = Field(default=None, max_length=20)
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"


class ChildCreate(ChildFields):
    pass


class ChildUpdate(ChildFields):
    pass


class ChildResponse(ChildFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

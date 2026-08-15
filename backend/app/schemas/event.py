import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventFields(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    start_at: datetime
    end_at: datetime
    location_name: str | None = Field(default=None, max_length=255)
    location_address: str | None = Field(default=None, max_length=255)
    status: Literal["DRAFT", "PUBLISHED", "COMPLETED"] = "DRAFT"

    @model_validator(mode="after")
    def validate_times(self) -> "EventFields":
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("日時にはタイムゾーンが必要です。")
        if self.end_at <= self.start_at:
            raise ValueError("終了日時は開始日時より後にしてください。")
        return self


class EventCreate(EventFields):
    pass


class EventUpdate(EventFields):
    pass


class EventResponse(EventFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    status: Literal["DRAFT", "PUBLISHED", "CANCELLED", "COMPLETED"]
    created_at: datetime
    updated_at: datetime

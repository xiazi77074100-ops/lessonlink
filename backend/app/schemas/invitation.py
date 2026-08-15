import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InvitationCreate(BaseModel):
    expires_at: datetime | None = None
    max_uses: int | None = Field(default=None, ge=1, le=10000)

    @model_validator(mode="after")
    def validate_expiry(self) -> "InvitationCreate":
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError("有効期限にはタイムゾーンが必要です。")
            if self.expires_at <= datetime.now(self.expires_at.tzinfo):
                raise ValueError("有効期限は未来の日時にしてください。")
        return self


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invitation_code: str
    expires_at: datetime | None
    max_uses: int | None
    used_count: int
    status: Literal["ACTIVE", "DISABLED", "EXPIRED"]
    created_at: datetime


class InvitationPublicResponse(BaseModel):
    invitation_code: str
    organization_name: str
    expires_at: datetime | None

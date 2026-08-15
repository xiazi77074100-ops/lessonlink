import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

OrganizationType = Literal[
    "サッカー", "野球", "空手", "ダンス", "バレエ", "ピアノ", "スイミング", "その他"
]


class OrganizationFields(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    organization_type: OrganizationType
    address: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None


class OrganizationCreate(OrganizationFields):
    owner_email: EmailStr
    owner_password: str = Field(min_length=8, max_length=128)
    owner_display_name: str = Field(min_length=1, max_length=100)


class OrganizationUpdate(OrganizationFields):
    pass


class OrganizationResponse(OrganizationFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan: str
    created_at: datetime
    updated_at: datetime


class OrganizationCreateResponse(BaseModel):
    organization: OrganizationResponse
    access_token: str
    token_type: str = "bearer"

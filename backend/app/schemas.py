import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import RequestStatus

# Must match the <option value="..."> entries in the frontend's role select.
Role = Literal["school-owner", "administrator", "principal", "other"]

ROLE_LABELS = {
    "school-owner": "School Owner",
    "administrator": "School Administrator",
    "principal": "Principal / Head Teacher",
    "other": "Other",
}


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class DemoRequestCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    school_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str
    role: Role
    message: str | None = Field(default=None, max_length=2000)
    # Honeypot: real users never see or fill this. Bots often do.
    website: str | None = Field(default=None, max_length=200)

    @field_validator("full_name", "school_name", mode="before")
    @classmethod
    def clean_text(cls, v):
        return _clean(v) if isinstance(v, str) else v

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, v):
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("phone", mode="before")
    @classmethod
    def clean_phone(cls, v):
        if not isinstance(v, str):
            raise ValueError("Enter a valid phone number.")
        stripped = re.sub(r"[\s\-().]", "", v)
        # Accepts 08109198446, +2348109198446, 2348109198446 and other intl formats
        if not re.fullmatch(r"\+?\d{7,15}", stripped):
            raise ValueError("Enter a valid phone number (7 to 15 digits).")
        return stripped

    @field_validator("message", mode="before")
    @classmethod
    def clean_message(cls, v):
        if v is None:
            return None
        v = v.strip()
        return v or None


class DemoRequestCreated(BaseModel):
    id: int
    message: str


class DemoRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    school_name: str
    email: str
    phone: str
    role: str
    message: str | None
    status: RequestStatus
    email_sent: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def as_utc(cls, v: datetime) -> datetime:
        # SQLite returns naive datetimes; everything is stored as UTC.
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v


class StatusUpdate(BaseModel):
    status: RequestStatus

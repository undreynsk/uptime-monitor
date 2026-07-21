from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class SiteCreate(BaseModel):
    url: HttpUrl
    name: str | None = None


class SiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    name: str | None
    is_active: bool
    created_at: datetime


class CheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    checked_at: datetime
    is_up: bool
    status_code: int | None
    response_time_ms: float | None
    error: str | None

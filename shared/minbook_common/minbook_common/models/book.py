from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Book(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    genre: str | None = None
    language: str = "zh"
    config_json: dict = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BookCreate(BaseModel):
    title: str
    genre: str | None = None
    language: str = "zh"
    config_json: dict = Field(default_factory=dict)


class BookUpdate(BaseModel):
    title: str | None = None
    genre: str | None = None
    config_json: dict | None = None

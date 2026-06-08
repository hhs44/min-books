from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Chapter(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    book_id: UUID
    chapter_number: int
    title: str | None = None
    content: str | None = None
    status: str = "draft"  # draft | written | audited | revised | finalized
    word_count: int = 0
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChapterImportRequest(BaseModel):
    book_id: UUID
    format: str  # txt | md | epub
    content: str | None = None  # base64 if file

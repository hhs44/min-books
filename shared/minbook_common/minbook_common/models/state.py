from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TruthFile(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    book_id: UUID
    file_type: str  # current_state | character_matrix | pending_hooks |
    #   chapter_summaries | subplot_board | emotional_arcs | particle_ledger
    content: dict  # JSONB
    version: int = 1
    updated_at: datetime | None = None


class StateSnapshot(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    book_id: UUID
    chapter_number: int | None = None
    snapshot_json: dict
    created_at: datetime | None = None

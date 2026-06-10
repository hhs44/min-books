"""no-op migration: book-service reuses existing shared.* schema (owned by minbook init scripts).
svc_book user has full shared.* permissions; no DDL needed here.

Revision ID: 0001_noop
Revises:
Create Date: 2026-06-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0001_noop"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""add notes column to documents

Revision ID: f1a2b3c4d5e6
Revises: e9f5a6b7c8d1
Create Date: 2026-03-10 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "e9f5a6b7c8d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "notes")

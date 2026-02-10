"""add document_type and ai_metadata to documents

Revision ID: a3b8f2c1d4e5
Revises: 0594fb9c5e75
Create Date: 2026-02-10 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b8f2c1d4e5'
down_revision: Union[str, Sequence[str], None] = '0594fb9c5e75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add document_type and ai_metadata columns to documents table."""
    op.add_column(
        "documents",
        sa.Column("document_type", sa.String(100), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("ai_metadata", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove document_type and ai_metadata columns."""
    op.drop_column("documents", "ai_metadata")
    op.drop_column("documents", "document_type")

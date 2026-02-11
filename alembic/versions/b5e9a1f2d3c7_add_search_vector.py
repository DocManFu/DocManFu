"""add search_vector tsvector column with GIN index

Revision ID: b5e9a1f2d3c7
Revises: a3b8f2c1d4e5
Create Date: 2026-02-10 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR


# revision identifiers, used by Alembic.
revision: str = "b5e9a1f2d3c7"
down_revision: Union[str, None] = "a3b8f2c1d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("search_vector", TSVECTOR, nullable=True))

    # Populate existing rows
    op.execute(
        """
        UPDATE documents SET search_vector = to_tsvector('english',
            coalesce(content_text, '') || ' ' ||
            coalesce(original_name, '') || ' ' ||
            coalesce(ai_generated_name, '')
        )
        """
    )

    # Create GIN index for fast full-text search
    op.create_index(
        "ix_documents_search_vector",
        "documents",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_documents_search_vector", table_name="documents")
    op.drop_column("documents", "search_vector")

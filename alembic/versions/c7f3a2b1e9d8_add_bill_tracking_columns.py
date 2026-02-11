"""add bill tracking columns

Revision ID: c7f3a2b1e9d8
Revises: b5e9a1f2d3c7
Create Date: 2026-02-10 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7f3a2b1e9d8"
down_revision: Union[str, None] = "b5e9a1f2d3c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("bill_status", sa.String(20), nullable=True))
    op.add_column("documents", sa.Column("bill_paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("bill_due_date", sa.Date(), nullable=True))

    op.create_index("ix_documents_bill_status", "documents", ["bill_status"])

    # Backfill existing bills as unpaid
    op.execute(
        "UPDATE documents SET bill_status = 'unpaid' WHERE document_type = 'bill' AND deleted_at IS NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_documents_bill_status", table_name="documents")
    op.drop_column("documents", "bill_due_date")
    op.drop_column("documents", "bill_paid_at")
    op.drop_column("documents", "bill_status")

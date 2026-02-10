"""add celery_task_id and result_data to processing_jobs

Revision ID: 0594fb9c5e75
Revises: 6225f1217fe2
Create Date: 2026-02-10 15:54:43.115812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0594fb9c5e75'
down_revision: Union[str, Sequence[str], None] = '6225f1217fe2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "processing_jobs",
        sa.Column("celery_task_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "processing_jobs",
        sa.Column("result_data", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_processing_jobs_celery_task_id",
        "processing_jobs",
        ["celery_task_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_processing_jobs_celery_task_id", table_name="processing_jobs")
    op.drop_column("processing_jobs", "result_data")
    op.drop_column("processing_jobs", "celery_task_id")

"""add users and ownership

Revision ID: d8e4f5a6b7c9
Revises: c7f3a2b1e9d8
Create Date: 2026-02-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "d8e4f5a6b7c9"
down_revision: Union[str, None] = "c7f3a2b1e9d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("api_key", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_api_key", "users", ["api_key"], unique=True)

    # 2. Add user_id FK to documents
    op.add_column("documents", sa.Column("user_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_documents_user_id", "documents", ["user_id"])
    op.create_foreign_key("fk_documents_user_id", "documents", "users", ["user_id"], ["id"])

    # 3. Add user_id FK to tags
    op.add_column("tags", sa.Column("user_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_tags_user_id", "tags", ["user_id"])
    op.create_foreign_key("fk_tags_user_id", "tags", "users", ["user_id"], ["id"])

    # 4. Drop old unique constraint on tags.name, add composite (name, user_id)
    op.drop_constraint("tags_name_key", "tags", type_="unique")
    op.create_unique_constraint("uq_tags_name_user_id", "tags", ["name", "user_id"])


def downgrade() -> None:
    # Reverse composite unique constraint
    op.drop_constraint("uq_tags_name_user_id", "tags", type_="unique")
    op.create_unique_constraint("tags_name_key", "tags", ["name"])

    # Remove user_id from tags
    op.drop_constraint("fk_tags_user_id", "tags", type_="foreignkey")
    op.drop_index("ix_tags_user_id", table_name="tags")
    op.drop_column("tags", "user_id")

    # Remove user_id from documents
    op.drop_constraint("fk_documents_user_id", "documents", type_="foreignkey")
    op.drop_index("ix_documents_user_id", table_name="documents")
    op.drop_column("documents", "user_id")

    # Drop users table
    op.drop_index("ix_users_api_key", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin

document_tags = Table(
    "document_tags",
    Base.metadata,
    Column("document_id", UUID(as_uuid=True), ForeignKey("documents.id"), primary_key=True),
    Column("tag_id", UUID(as_uuid=True), ForeignKey("tags.id"), primary_key=True),
)


class Tag(UUIDMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("name", "user_id", name="uq_tags_name_user_id"),
    )

    name: Mapped[str] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(7))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )

    owner: Mapped[Optional["User"]] = relationship(back_populates="tags")
    documents: Mapped[list["Document"]] = relationship(
        secondary=document_tags, back_populates="tags"
    )

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"


from app.models.document import Document  # noqa: E402
from app.models.user import User  # noqa: E402

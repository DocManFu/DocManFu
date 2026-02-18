import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Document(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    filename: Mapped[str] = mapped_column(String(500))
    original_name: Mapped[str] = mapped_column(String(500))
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_generated_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    document_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ai_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    file_path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(BigInteger)
    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    processed_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    bill_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, index=True
    )
    bill_paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    bill_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)

    owner: Mapped[Optional["User"]] = relationship(back_populates="documents")
    tags: Mapped[list["Tag"]] = relationship(
        secondary="document_tags", back_populates="documents"
    )
    processing_jobs: Mapped[list["ProcessingJob"]] = relationship(
        back_populates="document"
    )

    def __repr__(self) -> str:
        return f"<Document {self.filename}>"


# Avoid circular import issues - these are resolved at runtime
from app.models.processing_job import ProcessingJob  # noqa: E402
from app.models.tag import Tag  # noqa: E402
from app.models.user import User  # noqa: E402

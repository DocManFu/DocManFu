import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin


class JobType(str, enum.Enum):
    ocr = "ocr"
    ai_analysis = "ai_analysis"
    file_organization = "file_organization"


class JobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ProcessingJob(UUIDMixin, Base):
    __tablename__ = "processing_jobs"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
    job_type: Mapped[JobType] = mapped_column(Enum(JobType, name="job_type_enum"))
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status_enum"), default=JobStatus.pending
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    result_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="processing_jobs")

    def __repr__(self) -> str:
        return f"<ProcessingJob {self.job_type.value}:{self.status.value}>"


from app.models.document import Document  # noqa: E402

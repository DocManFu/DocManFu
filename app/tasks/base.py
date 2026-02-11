"""Base task class with database job tracking and progress updates."""

import logging
from datetime import datetime, timezone

from celery import Task

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.processing_job import JobStatus, ProcessingJob

logger = logging.getLogger(__name__)


class DocManFuTask(Task):
    """Base task that tracks progress in the ProcessingJob table.

    Subclasses call ``self.update_job_progress(job_id, progress, ...)``
    to persist progress.  On success / failure the job row is updated
    automatically via the Celery callback hooks.
    """

    abstract = True
    autoretry_for = (Exception,)
    max_retries = settings.CELERY_TASK_MAX_RETRIES
    default_retry_delay = settings.CELERY_TASK_RETRY_DELAY

    # ---- helpers --------------------------------------------------------

    def _get_db(self):
        """Return a new DB session (caller must close)."""
        return SessionLocal()

    def _get_doc_user_id(self, db, document_id) -> str | None:
        """Look up the user_id for a document (for event filtering)."""
        doc = db.get(Document, document_id)
        if doc and doc.user_id:
            return str(doc.user_id)
        return None

    def update_job_progress(self, job_id: str, progress: int, status: JobStatus | None = None):
        """Persist progress (0-100) and optional status change."""
        db = self._get_db()
        try:
            job = db.get(ProcessingJob, job_id)
            if job is None:
                logger.warning("ProcessingJob %s not found – skipping progress update", job_id)
                return
            job.progress = min(progress, 100)
            if status is not None:
                job.status = status
            if status == JobStatus.processing and job.started_at is None:
                job.started_at = datetime.now(timezone.utc)
            db.commit()

            from app.core.events import publish_event

            user_id = self._get_doc_user_id(db, job.document_id)
            publish_event("job.progress", {
                "job_id": job_id,
                "document_id": str(job.document_id),
                "job_type": job.job_type.value,
                "status": (status or job.status).value,
                "progress": min(progress, 100),
                "user_id": user_id,
            })
        finally:
            db.close()

    def mark_job_started(self, job_id: str):
        """Mark job as processing with started_at timestamp."""
        db = self._get_db()
        try:
            job = db.get(ProcessingJob, job_id)
            if job is None:
                return
            job.status = JobStatus.processing
            job.started_at = datetime.now(timezone.utc)
            job.progress = 0
            db.commit()

            from app.core.events import publish_event

            user_id = self._get_doc_user_id(db, job.document_id)
            publish_event("job.started", {
                "job_id": job_id,
                "document_id": str(job.document_id),
                "job_type": job.job_type.value,
                "status": "processing",
                "progress": 0,
                "user_id": user_id,
            })
        finally:
            db.close()

    def mark_job_completed(self, job_id: str, result_data: dict | None = None):
        """Mark job as completed with optional result payload."""
        db = self._get_db()
        try:
            job = db.get(ProcessingJob, job_id)
            if job is None:
                return
            job.status = JobStatus.completed
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc)
            if result_data is not None:
                job.result_data = result_data
            db.commit()

            from app.core.events import publish_event

            user_id = self._get_doc_user_id(db, job.document_id)
            publish_event("job.completed", {
                "job_id": job_id,
                "document_id": str(job.document_id),
                "job_type": job.job_type.value,
                "status": "completed",
                "progress": 100,
                "result_data": result_data,
                "user_id": user_id,
            })
        finally:
            db.close()

    def mark_job_failed(self, job_id: str, error_message: str):
        """Mark job as failed with error details."""
        db = self._get_db()
        try:
            job = db.get(ProcessingJob, job_id)
            if job is None:
                return
            job.status = JobStatus.failed
            job.error_message = error_message
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

            from app.core.events import publish_event

            user_id = self._get_doc_user_id(db, job.document_id)
            publish_event("job.failed", {
                "job_id": job_id,
                "document_id": str(job.document_id),
                "job_type": job.job_type.value,
                "status": "failed",
                "progress": job.progress,
                "error_message": error_message,
                "user_id": user_id,
            })
        finally:
            db.close()

    # ---- Celery callback hooks ------------------------------------------

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when the task fails after all retries are exhausted."""
        job_id = kwargs.get("job_id") or (args[0] if args else None)
        if job_id:
            self.mark_job_failed(job_id, str(exc))
        logger.error("Task %s failed: %s", self.name, exc)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when the task is about to be retried."""
        job_id = kwargs.get("job_id") or (args[0] if args else None)
        if job_id:
            db = self._get_db()
            try:
                job = db.get(ProcessingJob, job_id)
                if job:
                    job.error_message = f"Retrying: {exc}"
                    db.commit()
            finally:
                db.close()
        logger.warning("Task %s retrying: %s", self.name, exc)

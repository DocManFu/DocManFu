"""File organization task – renames and moves documents based on AI analysis."""

import logging

from app.core.celery_app import celery_app
from app.models.document import Document
from app.models.processing_job import JobStatus
from app.tasks.base import DocManFuTask

logger = logging.getLogger(__name__)


@celery_app.task(base=DocManFuTask, bind=True, name="tasks.process_file_organization")
def process_file_organization(self, job_id: str, document_id: str):
    """Organize document file based on AI-generated metadata.

    Pipeline (future session):
      1. Read AI analysis results from Document
      2. Rename file using ai_generated_name
      3. Update Document.file_path with new location
      4. Verify file integrity after move

    Args:
        job_id: ProcessingJob UUID (string)
        document_id: Document UUID (string)
    """
    self.mark_job_started(job_id)
    logger.info(
        "Starting file organization for document %s (job %s)", document_id, job_id
    )

    db = self._get_db()
    try:
        document = db.get(Document, document_id)
        if document is None:
            self.mark_job_failed(job_id, f"Document {document_id} not found")
            return

        # --- Phase 1: Check AI analysis results ---
        self.update_job_progress(job_id, 10, JobStatus.processing)

        if not document.ai_generated_name:
            self.mark_job_failed(job_id, "No AI-generated name – run AI analysis first")
            return

        # --- Phase 2: Rename / move file (stub) ---
        self.update_job_progress(job_id, 50, JobStatus.processing)
        logger.info(
            "File org stub: would rename %s to %s",
            document.filename,
            document.ai_generated_name,
        )

        # --- Phase 3: Verify and update DB (stub) ---
        self.update_job_progress(job_id, 80, JobStatus.processing)

        # --- Done ---
        result = {
            "document_id": document_id,
            "original_path": document.file_path,
            "new_path": None,
            "message": "File organization stub – full implementation in later session",
        }
        self.mark_job_completed(job_id, result_data=result)
        logger.info("File organization complete for document %s", document_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

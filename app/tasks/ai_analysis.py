"""AI analysis task – classifies documents and suggests names/tags."""

import logging

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.processing_job import JobStatus
from app.tasks.base import DocManFuTask

logger = logging.getLogger(__name__)


@celery_app.task(base=DocManFuTask, bind=True, name="tasks.process_ai_analysis")
def process_ai_analysis(self, job_id: str, document_id: str):
    """Analyze document content with AI for classification and naming.

    Pipeline (to be implemented in Session 6):
      1. Read extracted text from Document.content_text
      2. Send to configured AI provider
      3. Parse response for: document_type, suggested_name, tags, metadata
      4. Update Document record with AI suggestions

    Args:
        job_id: ProcessingJob UUID (string)
        document_id: Document UUID (string)
    """
    self.mark_job_started(job_id)
    logger.info("Starting AI analysis for document %s (job %s)", document_id, job_id)

    db = self._get_db()
    try:
        document = db.get(Document, document_id)
        if document is None:
            self.mark_job_failed(job_id, f"Document {document_id} not found")
            return

        # --- Phase 1: Read document text ---
        self.update_job_progress(job_id, 10, JobStatus.processing)

        if not document.content_text:
            self.mark_job_failed(job_id, "No text content available – run OCR first")
            return

        # --- Phase 2: AI classification (stub – implemented in Session 6) ---
        self.update_job_progress(job_id, 50, JobStatus.processing)
        logger.info("AI analysis stub: would analyze %s", document.original_name)

        # --- Phase 3: Parse and store results (stub) ---
        self.update_job_progress(job_id, 80, JobStatus.processing)

        # --- Done ---
        result = {
            "document_id": document_id,
            "suggested_name": None,
            "document_type": None,
            "suggested_tags": [],
            "confidence_score": 0.0,
            "message": "AI analysis stub – full implementation in Session 6",
        }
        self.mark_job_completed(job_id, result_data=result)
        logger.info("AI analysis complete for document %s", document_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

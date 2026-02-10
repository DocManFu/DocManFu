"""OCR processing task – extracts text from PDF documents."""

import logging

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.processing_job import JobStatus
from app.tasks.base import DocManFuTask

logger = logging.getLogger(__name__)


@celery_app.task(base=DocManFuTask, bind=True, name="tasks.process_ocr")
def process_ocr(self, job_id: str, document_id: str):
    """Run OCR on a document PDF and extract text content.

    Pipeline (to be implemented in Session 5):
      1. Run ocrmypdf on the uploaded file
      2. Extract text content from the resulting PDF
      3. Save searchable PDF alongside original
      4. Update Document.content_text with extracted text

    Args:
        job_id: ProcessingJob UUID (string)
        document_id: Document UUID (string)
    """
    self.mark_job_started(job_id)
    logger.info("Starting OCR for document %s (job %s)", document_id, job_id)

    db = self._get_db()
    try:
        document = db.get(Document, document_id)
        if document is None:
            self.mark_job_failed(job_id, f"Document {document_id} not found")
            return

        # --- Phase 1: Validate file exists ---
        self.update_job_progress(job_id, 10, JobStatus.processing)

        # --- Phase 2: Run OCR (stub – implemented in Session 5) ---
        self.update_job_progress(job_id, 50, JobStatus.processing)
        logger.info("OCR stub: would process %s", document.file_path)

        # --- Phase 3: Extract text (stub) ---
        self.update_job_progress(job_id, 80, JobStatus.processing)

        # --- Done ---
        result = {
            "document_id": document_id,
            "pages_processed": 0,
            "text_extracted": False,
            "message": "OCR stub – full implementation in Session 5",
        }
        self.mark_job_completed(job_id, result_data=result)
        logger.info("OCR complete for document %s", document_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

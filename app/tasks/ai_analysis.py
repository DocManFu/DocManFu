"""AI analysis task – classifies documents and suggests names/tags."""

import logging

from app.core.celery_app import celery_app
from app.models.document import Document
from app.models.processing_job import JobStatus
from app.models.tag import Tag
from app.tasks.base import DocManFuTask

logger = logging.getLogger(__name__)


@celery_app.task(base=DocManFuTask, bind=True, name="tasks.process_ai_analysis")
def process_ai_analysis(self, job_id: str, document_id: str):
    """Analyze document content with AI for classification and naming.

    Pipeline:
      1. Read extracted text from Document.content_text
      2. Send to configured AI provider
      3. Parse response for: document_type, suggested_name, tags, metadata
      4. Update Document record with AI suggestions
      5. Create/associate suggested tags

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

        # --- Phase 1: Read document text (10%) ---
        self.update_job_progress(job_id, 10, JobStatus.processing)

        if not document.content_text:
            self.mark_job_failed(job_id, "No text content available – run OCR first")
            return

        text = document.content_text
        logger.info(
            "Analyzing document '%s' (%d chars of text)",
            document.original_name,
            len(text),
        )

        # --- Phase 2: Call AI provider (50%) ---
        self.update_job_progress(job_id, 20, JobStatus.processing)

        from app.core.ai_provider import analyze_document

        try:
            result = analyze_document(text, document.original_name)
        except ValueError as exc:
            # Config error (no provider, no key) — don't retry
            self.mark_job_failed(job_id, str(exc))
            return

        self.update_job_progress(job_id, 60, JobStatus.processing)
        logger.info(
            "AI classified '%s' as type=%s, suggested_name='%s', confidence=%.2f",
            document.original_name,
            result.document_type,
            result.suggested_name,
            result.confidence_score,
        )

        # --- Phase 3: Update document record (80%) ---
        self.update_job_progress(job_id, 70, JobStatus.processing)

        document.ai_generated_name = result.suggested_name
        document.document_type = result.document_type
        document.ai_metadata = result.extracted_metadata

        # --- Phase 4: Create/associate suggested tags (90%) ---
        self.update_job_progress(job_id, 80, JobStatus.processing)

        for tag_name in result.suggested_tags:
            tag_name = tag_name.strip().lower()[:100]
            if not tag_name:
                continue
            # Find existing tag or create new one
            tag = db.query(Tag).filter(Tag.name == tag_name).first()
            if tag is None:
                tag = Tag(name=tag_name, color="#6B7280")
                db.add(tag)
                db.flush()
                logger.info("Created new tag: %s", tag_name)
            if tag not in document.tags:
                document.tags.append(tag)

        db.commit()
        self.update_job_progress(job_id, 90, JobStatus.processing)

        # --- Done ---
        job_result = {
            "document_id": document_id,
            "suggested_name": result.suggested_name,
            "document_type": result.document_type,
            "suggested_tags": result.suggested_tags,
            "extracted_metadata": result.extracted_metadata,
            "confidence_score": result.confidence_score,
        }
        self.mark_job_completed(job_id, result_data=job_result)
        logger.info("AI analysis complete for document %s", document_id)

    except ValueError:
        # Already handled above — re-raise would trigger retry
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

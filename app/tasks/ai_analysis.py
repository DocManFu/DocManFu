"""AI analysis task – classifies documents and suggests names/tags."""

import logging
from datetime import date
from pathlib import Path

from app.core.celery_app import celery_app
from app.core.config import settings
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

        # --- Phase 1: Prepare for analysis (10%) ---
        self.update_job_progress(job_id, 10, JobStatus.processing)

        text = document.content_text
        pdf_path = Path(settings.UPLOAD_DIR) / document.file_path

        # --- Phase 2: Text-first analysis, vision fallback for poor text (50%) ---
        self.update_job_progress(job_id, 20, JobStatus.processing)

        from app.core.ai_provider import (
            _load_ai_config,
            analyze_document,
            analyze_document_vision,
        )

        ai_config = _load_ai_config()
        result = None
        vision_used = False

        # Use text analysis when we have good extracted text
        if text:
            logger.info(
                "Using text-based analysis for '%s' (%d chars)",
                document.original_name,
                len(text),
            )
            try:
                result = analyze_document(
                    text, document.original_name, config=ai_config
                )
            except ValueError as exc:
                self.mark_job_failed(job_id, str(exc))
                return

        # Fall back to vision when text is missing or empty (image-only PDFs,
        # handwritten docs, poorly scanned content)
        if result is None and pdf_path.exists():
            logger.info(
                "No extracted text for '%s', trying vision analysis",
                document.original_name,
            )
            try:
                if document.mime_type.startswith("image/"):
                    # Image file: encode directly as base64 PNG
                    import base64
                    import io

                    from PIL import Image

                    img = Image.open(str(pdf_path))
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    buf.seek(0)
                    b64 = base64.b64encode(buf.read()).decode("utf-8")
                    images = [b64]
                else:
                    # PDF file: render pages to images
                    from app.core.pdf_renderer import render_pdf_pages

                    images = render_pdf_pages(
                        str(pdf_path),
                        max_pages=int(ai_config.get("ai_max_pages") or 5),
                        dpi=int(ai_config.get("ai_vision_dpi") or 150),
                    )

                if images:
                    result = analyze_document_vision(
                        images, document.original_name, config=ai_config
                    )
                    vision_used = True
            except ValueError as exc:
                self.mark_job_failed(job_id, str(exc))
                return
            except Exception as exc:
                logger.warning(
                    "Vision analysis also failed for '%s': %s",
                    document.original_name,
                    exc,
                )

        if result is None:
            self.mark_job_failed(
                job_id,
                "No analysis possible — no text content and vision analysis failed",
            )
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

        # --- Bill tracking ---
        if result.document_type in ("bill", "invoice"):
            # Only set to unpaid if not already paid/dismissed
            if document.bill_status not in ("paid", "dismissed"):
                document.bill_status = "unpaid"
            # Parse due_date from extracted metadata
            raw_due = result.extracted_metadata.get("due_date")
            if raw_due:
                try:
                    document.bill_due_date = date.fromisoformat(raw_due)
                except (ValueError, TypeError):
                    logger.warning("Could not parse due_date '%s'", raw_due)
        elif document.bill_status == "unpaid":
            # Reprocessed and no longer a bill — clear unpaid status
            document.bill_status = None
            document.bill_due_date = None

        # --- Phase 4: Create/associate suggested tags (90%) ---
        self.update_job_progress(job_id, 80, JobStatus.processing)

        doc_user_id = document.user_id
        for tag_name in result.suggested_tags:
            tag_name = tag_name.strip().lower()[:100]
            if not tag_name:
                continue
            # Find existing tag or create new one (scoped to document owner)
            tag = (
                db.query(Tag)
                .filter(Tag.name == tag_name, Tag.user_id == doc_user_id)
                .first()
            )
            if tag is None:
                tag = Tag(name=tag_name, color="#6B7280", user_id=doc_user_id)
                db.add(tag)
                db.flush()
                logger.info("Created new tag: %s", tag_name)
            if tag not in document.tags:
                document.tags.append(tag)

        db.commit()

        from app.core.events import publish_event

        changes = ["ai_generated_name", "document_type", "ai_metadata", "tags"]
        if result.document_type in ("bill", "invoice"):
            changes.append("bill_status")
        publish_event(
            "document.updated",
            {
                "document_id": document_id,
                "changes": changes,
                "user_id": str(doc_user_id) if doc_user_id else None,
            },
        )

        # Update search vector
        from app.core.search import update_search_vector

        update_search_vector(db, document_id)

        self.update_job_progress(job_id, 90, JobStatus.processing)

        # --- Done ---
        job_result = {
            "document_id": document_id,
            "suggested_name": result.suggested_name,
            "document_type": result.document_type,
            "suggested_tags": result.suggested_tags,
            "extracted_metadata": result.extracted_metadata,
            "confidence_score": result.confidence_score,
            "vision_used": vision_used,
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

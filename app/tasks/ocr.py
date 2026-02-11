"""OCR processing task – extracts text from documents using ocrmypdf (PDFs) or pytesseract (images)."""

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import ocrmypdf
from pdfminer.high_level import extract_text

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.document import Document
from app.models.processing_job import JobStatus, JobType, ProcessingJob
from app.tasks.base import DocManFuTask

logger = logging.getLogger(__name__)


def _is_image(mime_type: str) -> bool:
    """Check if the MIME type is an image format."""
    return mime_type.startswith("image/")


@celery_app.task(base=DocManFuTask, bind=True, name="tasks.process_ocr")
def process_ocr(self, job_id: str, document_id: str):
    """Run OCR on a document PDF and extract text content.

    Pipeline:
      1. Validate the uploaded file exists on disk
      2. Run ocrmypdf to produce a searchable PDF
      3. Extract text from the searchable PDF via pdfminer
      4. Replace the original PDF with the searchable version
      5. Update Document.content_text and processed_date

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

        # --- Phase 1: Validate file exists (10%) ---
        self.update_job_progress(job_id, 10, JobStatus.processing)
        input_path = Path(settings.UPLOAD_DIR) / document.file_path
        if not input_path.exists():
            self.mark_job_failed(job_id, f"File not found: {document.file_path}")
            return
        logger.info("Found file at %s (%d bytes)", input_path, document.file_size)

        # --- Phase 2+3: OCR and text extraction (branched by file type) ---
        self.update_job_progress(job_id, 20, JobStatus.processing)

        if _is_image(document.mime_type):
            # --- Image path: pytesseract ---
            extracted_text, page_count = _ocr_image(self, job_id, input_path)
            if extracted_text is None:
                return  # job already marked as failed
        else:
            # --- PDF path: ocrmypdf + pdfminer ---
            extracted_text, page_count = _ocr_pdf(self, job_id, input_path, document)
            if extracted_text is None:
                return  # job already marked as failed

        # --- Phase 5: Update document record (90%) ---
        self.update_job_progress(job_id, 90, JobStatus.processing)

        document.content_text = extracted_text if extracted_text else None
        document.processed_date = datetime.now(timezone.utc)
        db.commit()

        # Update search vector
        from app.core.search import update_search_vector

        update_search_vector(db, document_id)

        # --- Done ---
        result = {
            "document_id": document_id,
            "pages_processed": page_count,
            "text_length": len(extracted_text),
            "text_extracted": bool(extracted_text),
        }
        self.mark_job_completed(job_id, result_data=result)
        logger.info(
            "OCR complete for document %s: %d pages, %d chars extracted",
            document_id,
            page_count,
            len(extracted_text),
        )

        # --- Chain: dispatch AI analysis if provider is configured ---
        if settings.AI_PROVIDER.lower() not in ("none", ""):
            _dispatch_ai_analysis(db, document_id)

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _ocr_image(task, job_id: str, input_path: Path) -> tuple[str | None, int]:
    """Run OCR on an image file using pytesseract. Returns (extracted_text, page_count) or (None, 0) on failure."""
    import pytesseract
    from PIL import Image

    try:
        img = Image.open(input_path)
        extracted_text = pytesseract.image_to_string(img, lang=settings.OCR_LANGUAGE)
    except Exception as exc:
        logger.warning("Image OCR failed for %s: %s", input_path, exc)
        extracted_text = ""

    extracted_text = extracted_text.strip()

    task.update_job_progress(job_id, 80, JobStatus.processing)
    logger.info("Extracted %d characters from image %s", len(extracted_text), input_path.name)

    return extracted_text, 1


def _ocr_pdf(task, job_id: str, input_path: Path, document) -> tuple[str | None, int]:
    """Run OCR on a PDF file using ocrmypdf + pdfminer. Returns (extracted_text, page_count) or (None, 0) on failure."""
    # Write OCR output to a temp file, then swap on success
    output_fd = tempfile.NamedTemporaryFile(
        suffix=".pdf", delete=False, dir=input_path.parent
    )
    output_path = Path(output_fd.name)
    output_fd.close()

    try:
        languages = settings.OCR_LANGUAGE.split("+")
        ocrmypdf.ocr(
            input_file=str(input_path),
            output_file=str(output_path),
            language=languages,
            image_dpi=settings.OCR_DPI,
            skip_text=settings.OCR_SKIP_TEXT,
            clean=settings.OCR_CLEAN,
            progress_bar=False,
        )
    except ocrmypdf.PriorOcrFoundError:
        logger.info("PDF already contains OCR text, skipping re-OCR")
        output_path.unlink(missing_ok=True)
        output_path = input_path
    except ocrmypdf.exceptions.EncryptedPdfError:
        output_path.unlink(missing_ok=True)
        task.mark_job_failed(job_id, "PDF is encrypted and cannot be processed")
        return None, 0
    except ocrmypdf.exceptions.InputFileError as exc:
        output_path.unlink(missing_ok=True)
        task.mark_job_failed(job_id, f"Invalid input PDF: {exc}")
        return None, 0

    task.update_job_progress(job_id, 50, JobStatus.processing)
    logger.info("OCR processing complete for %s", document.file_path)

    # Extract text from searchable PDF
    task.update_job_progress(job_id, 60, JobStatus.processing)

    text_source = output_path if output_path.exists() else input_path
    try:
        extracted_text = extract_text(str(text_source))
    except Exception as exc:
        logger.warning("Text extraction failed for %s: %s", text_source, exc)
        extracted_text = ""

    extracted_text = extracted_text.strip()

    task.update_job_progress(job_id, 80, JobStatus.processing)
    logger.info(
        "Extracted %d characters of text from %s",
        len(extracted_text),
        document.original_name,
    )

    # Replace original with searchable PDF
    if output_path != input_path and output_path.exists():
        output_path.replace(input_path)
        logger.info("Replaced original PDF with searchable version")

    page_count = _count_pdf_pages(input_path)
    return extracted_text, page_count


def _count_pdf_pages(pdf_path: Path) -> int:
    """Count the number of pages in a PDF file."""
    try:
        from pdfminer.pdfpage import PDFPage

        with open(pdf_path, "rb") as f:
            return sum(1 for _ in PDFPage.get_pages(f))
    except Exception:
        return 0


def _dispatch_ai_analysis(db, document_id: str):
    """Create an AI analysis job and dispatch it to Celery."""
    try:
        ai_job = ProcessingJob(document_id=document_id, job_type=JobType.ai_analysis)
        db.add(ai_job)
        db.commit()
        db.refresh(ai_job)

        from app.tasks.ai_analysis import process_ai_analysis

        task = process_ai_analysis.delay(str(ai_job.id), str(document_id))
        ai_job.celery_task_id = task.id
        db.commit()

        logger.info(
            "Dispatched AI analysis job %s (celery task %s) for document %s",
            ai_job.id,
            task.id,
            document_id,
        )
    except Exception as exc:
        logger.error("Failed to dispatch AI analysis for document %s: %s", document_id, exc)
        db.rollback()

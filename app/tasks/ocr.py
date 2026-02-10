"""OCR processing task – extracts text from PDF documents using ocrmypdf."""

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import ocrmypdf
from pdfminer.high_level import extract_text

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.document import Document
from app.models.processing_job import JobStatus
from app.tasks.base import DocManFuTask

logger = logging.getLogger(__name__)


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

        # --- Phase 2: Run ocrmypdf (50%) ---
        self.update_job_progress(job_id, 20, JobStatus.processing)

        # Write OCR output to a temp file, then swap on success
        output_fd = tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False, dir=input_path.parent
        )
        output_path = Path(output_fd.name)
        output_fd.close()

        try:
            # language expects a list: "eng+fra" → ["eng", "fra"]
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
            # PDF already has OCR text — use it as-is
            logger.info("PDF already contains OCR text, skipping re-OCR")
            output_path.unlink(missing_ok=True)
            output_path = input_path
        except ocrmypdf.exceptions.EncryptedPdfError:
            output_path.unlink(missing_ok=True)
            self.mark_job_failed(job_id, "PDF is encrypted and cannot be processed")
            return
        except ocrmypdf.exceptions.InputFileError as exc:
            output_path.unlink(missing_ok=True)
            self.mark_job_failed(job_id, f"Invalid input PDF: {exc}")
            return

        self.update_job_progress(job_id, 50, JobStatus.processing)
        logger.info("OCR processing complete for %s", document.file_path)

        # --- Phase 3: Extract text from searchable PDF (80%) ---
        self.update_job_progress(job_id, 60, JobStatus.processing)

        text_source = output_path if output_path.exists() else input_path
        try:
            extracted_text = extract_text(str(text_source))
        except Exception as exc:
            logger.warning("Text extraction failed for %s: %s", text_source, exc)
            extracted_text = ""

        # Clean up whitespace but preserve structure
        extracted_text = extracted_text.strip()

        self.update_job_progress(job_id, 80, JobStatus.processing)
        logger.info(
            "Extracted %d characters of text from %s",
            len(extracted_text),
            document.original_name,
        )

        # --- Phase 4: Replace original with searchable PDF ---
        if output_path != input_path and output_path.exists():
            output_path.replace(input_path)
            logger.info("Replaced original PDF with searchable version")

        # --- Phase 5: Update document record (90%) ---
        self.update_job_progress(job_id, 90, JobStatus.processing)

        document.content_text = extracted_text if extracted_text else None
        document.processed_date = datetime.now(timezone.utc)
        db.commit()

        # Count pages for result data
        page_count = _count_pdf_pages(input_path)

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
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _count_pdf_pages(pdf_path: Path) -> int:
    """Count the number of pages in a PDF file."""
    try:
        from pdfminer.pdfpage import PDFPage

        with open(pdf_path, "rb") as f:
            return sum(1 for _ in PDFPage.get_pages(f))
    except Exception:
        return 0

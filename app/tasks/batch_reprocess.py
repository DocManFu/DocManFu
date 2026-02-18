"""Celery task for batch reprocessing documents with pause/resume support."""

import logging
from pathlib import Path

import redis

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.events import publish_event
from app.core.search import update_search_vector
from app.models.document import Document
from app.tasks.base import DocManFuTask

logger = logging.getLogger(__name__)

PAUSE_KEY_PREFIX = "batch_reprocess:pause:"
CANCEL_KEY_PREFIX = "batch_reprocess:cancel:"
SKIP_KEY_PREFIX = "batch_reprocess:skip:"


def _redis():
    return redis.Redis.from_url(settings.REDIS_URL)


def is_paused(task_id: str) -> bool:
    r = _redis()
    val = r.get(f"{PAUSE_KEY_PREFIX}{task_id}")
    r.close()
    return val == b"1"


def is_cancelled(task_id: str) -> bool:
    r = _redis()
    val = r.get(f"{CANCEL_KEY_PREFIX}{task_id}")
    r.close()
    return val == b"1"


def set_paused(task_id: str, paused: bool):
    r = _redis()
    r.set(f"{PAUSE_KEY_PREFIX}{task_id}", "1" if paused else "0", ex=86400)
    r.close()


def set_cancelled(task_id: str):
    r = _redis()
    r.set(f"{CANCEL_KEY_PREFIX}{task_id}", "1", ex=86400)
    r.close()


def should_skip(task_id: str) -> bool:
    r = _redis()
    val = r.get(f"{SKIP_KEY_PREFIX}{task_id}")
    r.close()
    return val == b"1"


def set_skip(task_id: str):
    r = _redis()
    r.set(f"{SKIP_KEY_PREFIX}{task_id}", "1", ex=86400)
    r.close()


def clear_skip(task_id: str):
    r = _redis()
    r.delete(f"{SKIP_KEY_PREFIX}{task_id}")
    r.close()


def cleanup_keys(task_id: str):
    r = _redis()
    r.delete(
        f"{PAUSE_KEY_PREFIX}{task_id}",
        f"{CANCEL_KEY_PREFIX}{task_id}",
        f"{SKIP_KEY_PREFIX}{task_id}",
    )
    r.close()


ACTIVE_TASK_KEY = "batch_reprocess:active_task"


def get_active_task() -> str | None:
    r = _redis()
    val = r.get(ACTIVE_TASK_KEY)
    r.close()
    return val.decode() if val else None


def set_active_task(task_id: str | None):
    r = _redis()
    if task_id:
        r.set(ACTIVE_TASK_KEY, task_id, ex=86400)
    else:
        r.delete(ACTIVE_TASK_KEY)
    r.close()


@celery_app.task(base=DocManFuTask, bind=True, name="tasks.batch_reprocess")
def batch_reprocess_task(
    self, document_ids: list[str], user_id: str, job_type: str = "ocr"
):
    """Reprocess documents one at a time with progress, pause/resume, and cancel support."""
    import time

    from app.db.session import SessionLocal

    task_id = self.request.id

    # Prevent concurrent batch tasks
    existing = get_active_task()
    if existing and existing != task_id:
        publish_event(
            "reprocess.completed",
            {
                "task_id": task_id,
                "user_id": user_id,
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "errors": [
                    {
                        "document": "(blocked)",
                        "error": f"Another batch task is already running: {existing}",
                    }
                ],
                "total": len(document_ids),
                "status": "blocked",
            },
        )
        return {"status": "blocked", "reason": "Another batch task is running"}

    set_active_task(task_id)
    db = SessionLocal()
    total = len(document_ids)

    stats = {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }

    def publish_progress(current_name: str = "", status: str = ""):
        publish_event(
            "reprocess.progress",
            {
                "task_id": task_id,
                "user_id": user_id,
                "current": stats["processed"],
                "total": total,
                "succeeded": stats["succeeded"],
                "failed": stats["failed"],
                "skipped": stats["skipped"],
                "current_document": current_name,
                "paused": is_paused(task_id),
                "status": status or f"Processing {stats['processed']}/{total}...",
            },
        )

    try:
        publish_progress(status=f"Starting batch reprocess of {total} documents...")

        for i, doc_id in enumerate(document_ids):
            # Check for cancel
            if is_cancelled(task_id):
                publish_event(
                    "reprocess.cancelled",
                    {
                        "task_id": task_id,
                        "user_id": user_id,
                        **stats,
                        "total": total,
                        "status": f"Cancelled after {stats['processed']}/{total} documents",
                    },
                )
                cleanup_keys(task_id)
                set_active_task(None)
                db.close()
                return {**stats, "total": total, "status": "cancelled"}

            # Check for pause — poll until unpaused or cancelled
            while is_paused(task_id):
                publish_progress(status=f"Paused at {stats['processed']}/{total}")
                time.sleep(2)
                if is_cancelled(task_id):
                    break
            if is_cancelled(task_id):
                continue  # Will hit the cancel check at top of loop

            doc = (
                db.query(Document)
                .filter(Document.id == doc_id, Document.deleted_at.is_(None))
                .first()
            )
            if not doc:
                stats["skipped"] += 1
                stats["processed"] += 1
                continue

            doc_name = doc.original_name or doc.filename
            publish_progress(current_name=doc_name, status=f"Processing: {doc_name}")

            abs_path = Path(settings.UPLOAD_DIR) / doc.file_path
            if not abs_path.exists():
                stats["skipped"] += 1
                stats["processed"] += 1
                stats["errors"].append(
                    {"document": doc_name, "error": "File not found on disk"}
                )
                continue

            try:
                # Clear any previous skip flag before starting
                clear_skip(task_id)

                if job_type == "ocr":
                    _run_ocr(db, doc, abs_path, task_id=task_id)
                elif job_type == "ai":
                    _run_ai_analysis(db, doc)

                stats["succeeded"] += 1
            except _SkipDocument:
                stats["skipped"] += 1
                clear_skip(task_id)
                logger.info("Skipped document %s (%s)", doc_id, doc_name)
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append({"document": doc_name, "error": str(e)})
                logger.exception("Error reprocessing document %s", doc_id)

            stats["processed"] += 1

            # Progress on every document
            publish_progress(current_name=doc_name)

    except Exception as e:
        logger.exception("Fatal error in batch reprocess")
        stats["errors"].append({"document": "(fatal)", "error": str(e)})
    finally:
        db.close()
        cleanup_keys(task_id)
        set_active_task(None)

    result = {
        **stats,
        "total": total,
        "task_id": task_id,
        "user_id": user_id,
        "status": "completed",
    }

    publish_event("reprocess.completed", result)
    return result


def _run_ocr(db, doc: Document, abs_path: Path, task_id: str | None = None):
    """Extract text from a document. Fast path: embedded text. Slow path: Tesseract OCR."""
    mime = doc.mime_type or ""

    if mime == "application/pdf":
        _process_pdf(db, doc, abs_path, task_id=task_id)
    elif mime.startswith("image/"):
        _process_image(db, doc, abs_path)
    elif mime in ("text/plain", "text/csv", "text/html", "text/xml"):
        try:
            doc.content_text = abs_path.read_text(errors="replace")
        except Exception:
            pass
        update_search_vector(db, doc.id)
        db.commit()
    else:
        # Nothing we can extract text from
        update_search_vector(db, doc.id)
        db.commit()


def _process_pdf(db, doc: Document, abs_path: Path, task_id: str | None = None):
    """Extract text from PDF — pymupdf first (instant), ocrmypdf fallback (slow, interruptible)."""
    import fitz

    try:
        pdf_doc = fitz.open(str(abs_path))
        pages = []
        for page in pdf_doc:
            text = page.get_text()
            if text.strip():
                pages.append(text.strip())
        pdf_doc.close()

        if pages:
            doc.content_text = "\n\n".join(pages)
            update_search_vector(db, doc.id)
            db.commit()
            return
    except Exception:
        pass

    # No embedded text — scanned PDF, use ocrmypdf in a subprocess we can kill
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        proc = subprocess.Popen(
            [
                "python3",
                "-m",
                "ocrmypdf",
                "--skip-text",
                "--optimize",
                "0",
                str(abs_path),
                tmp_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Poll the process, checking for skip every 2 seconds
        while proc.poll() is None:
            if task_id and should_skip(task_id):
                proc.kill()
                proc.wait()
                logger.info("OCR skipped for document %s (user requested skip)", doc.id)
                raise _SkipDocument()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

        if proc.returncode == 0:
            out_doc = fitz.open(tmp_path)
            pages = []
            for page in out_doc:
                text = page.get_text()
                if text.strip():
                    pages.append(text.strip())
            out_doc.close()
            if pages:
                doc.content_text = "\n\n".join(pages)
    except _SkipDocument:
        raise
    except Exception:
        pass
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    update_search_vector(db, doc.id)
    db.commit()


class _SkipDocument(Exception):
    """Raised when user requests to skip the current document."""

    pass


def _process_image(db, doc: Document, abs_path: Path):
    """OCR an image using pytesseract."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(str(abs_path))
        text = pytesseract.image_to_string(img)
        if text.strip():
            doc.content_text = text.strip()
    except Exception:
        pass

    update_search_vector(db, doc.id)
    db.commit()


def _run_ai_analysis(db, doc: Document):
    """Run AI analysis on a single document synchronously."""
    from datetime import date

    from app.core.ai_provider import (
        _load_ai_config,
        analyze_document,
        analyze_document_vision,
    )
    from app.core.search import update_search_vector
    from app.models.tag import Tag

    text = doc.content_text
    pdf_path = Path(settings.UPLOAD_DIR) / doc.file_path
    ai_config = _load_ai_config()
    result = None

    # Text-based analysis
    if text:
        result = analyze_document(text, doc.original_name, config=ai_config)

    # Vision fallback
    if result is None and pdf_path.exists():
        try:
            if doc.mime_type and doc.mime_type.startswith("image/"):
                import base64
                import io

                from PIL import Image

                img = Image.open(str(pdf_path))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                images = [base64.b64encode(buf.read()).decode("utf-8")]
            else:
                from app.core.pdf_renderer import render_pdf_pages

                images = render_pdf_pages(
                    str(pdf_path),
                    max_pages=int(ai_config.get("ai_max_pages") or 5),
                    dpi=int(ai_config.get("ai_vision_dpi") or 150),
                )

            if images:
                result = analyze_document_vision(
                    images, doc.original_name, config=ai_config
                )
        except Exception as e:
            logger.warning("Vision analysis failed for '%s': %s", doc.original_name, e)

    if result is None:
        raise RuntimeError("No analysis possible — no text and vision failed")

    # Update document
    doc.ai_generated_name = result.suggested_name
    doc.document_type = result.document_type
    doc.ai_metadata = result.extracted_metadata

    # Bill tracking
    if result.document_type in ("bill", "invoice"):
        if doc.bill_status not in ("paid", "dismissed"):
            doc.bill_status = "unpaid"
        raw_due = result.extracted_metadata.get("due_date")
        if raw_due:
            try:
                doc.bill_due_date = date.fromisoformat(raw_due)
            except (ValueError, TypeError):
                pass
    elif getattr(doc, "bill_status", None) == "unpaid":
        doc.bill_status = None
        doc.bill_due_date = None

    # Tags
    doc_user_id = doc.user_id
    for tag_name in result.suggested_tags:
        tag_name = tag_name.strip().lower()[:100]
        if not tag_name:
            continue
        tag = (
            db.query(Tag)
            .filter(Tag.name == tag_name, Tag.user_id == doc_user_id)
            .first()
        )
        if tag is None:
            tag = Tag(name=tag_name, color="#6B7280", user_id=doc_user_id)
            db.add(tag)
            db.flush()
        if tag not in doc.tags:
            doc.tags.append(tag)

    db.commit()
    update_search_vector(db, doc.id)

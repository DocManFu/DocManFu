"""Import & batch processing API (admin-only)."""

import logging
import tempfile
from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.deps import get_db
from app.models.document import Document
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/import", tags=["import"])


class ImportTaskResponse(BaseModel):
    task_id: str
    filename: str
    status: str


class ImportStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: dict | None = None
    result: dict | None = None


@router.post("/evernote", response_model=ImportTaskResponse)
async def import_evernote(
    file: UploadFile,
    admin: User = Depends(require_admin),
):
    """Upload an ENEX file and start background import."""
    if not file.filename or not file.filename.lower().endswith(".enex"):
        raise HTTPException(status_code=400, detail="File must be an .enex file")

    # Save to uploads/_imports/ (shared volume between api and worker)
    import_dir = Path(settings.UPLOAD_DIR) / "_imports"
    import_dir.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".enex", dir=str(import_dir))
    try:
        total_size = 0
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            tmp.write(chunk)
            total_size += len(chunk)
        tmp.close()
    except Exception as e:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")

    file_size_mb = total_size / (1024 * 1024)
    logger.info(
        "Admin '%s' started ENEX import: %s (%.1f MB)",
        admin.username,
        file.filename,
        file_size_mb,
    )

    # Dispatch Celery task
    from app.tasks.import_evernote import import_evernote_task

    task = import_evernote_task.delay(tmp.name, str(admin.id), file.filename)

    return ImportTaskResponse(
        task_id=task.id,
        filename=file.filename or "import.enex",
        status="started",
    )


@router.get("/status/{task_id}", response_model=ImportStatusResponse)
def import_status(
    task_id: str,
    admin: User = Depends(require_admin),
):
    """Check the status of an import task."""
    result = AsyncResult(task_id, app=celery_app)

    response = ImportStatusResponse(task_id=task_id, status=result.state)

    if result.state == "PROGRESS":
        response.progress = result.info
    elif result.state == "SUCCESS":
        response.result = result.result
    elif result.state == "FAILURE":
        response.result = {"error": str(result.result)}

    return response


@router.post("/cancel/{task_id}")
def cancel_import(
    task_id: str,
    admin: User = Depends(require_admin),
):
    """Cancel a running import task."""
    celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
    logger.info("Admin '%s' cancelled import task %s", admin.username, task_id)
    return {"detail": "Import cancelled", "task_id": task_id}


# --- Batch Reprocess ---


class ReprocessRequest(BaseModel):
    job_type: str = "ocr"  # "ocr" or "ai"
    filter: str = "all"  # "all", "no_text", "no_ai"


@router.post("/reprocess")
def start_batch_reprocess(
    req: ReprocessRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Start batch reprocessing of documents."""
    query = db.query(Document.id).filter(Document.deleted_at.is_(None))

    if req.filter == "no_text":
        query = query.filter(
            (Document.content_text.is_(None)) | (Document.content_text == "")
        )
    elif req.filter == "no_ai":
        # Only docs that have text but no AI analysis (AI needs text to work with)
        query = query.filter(
            Document.ai_metadata.is_(None),
            Document.content_text.isnot(None),
            Document.content_text != "",
        )

    doc_ids = [str(row[0]) for row in query.all()]

    if not doc_ids:
        raise HTTPException(status_code=400, detail="No documents match the filter")

    from app.tasks.batch_reprocess import batch_reprocess_task, get_active_task

    active = get_active_task()
    if active:
        raise HTTPException(
            status_code=409, detail="A batch reprocess is already running"
        )

    task = batch_reprocess_task.delay(doc_ids, str(admin.id), req.job_type)

    logger.info(
        "Admin '%s' started batch reprocess: %d documents, type=%s, filter=%s",
        admin.username,
        len(doc_ids),
        req.job_type,
        req.filter,
    )

    return {
        "task_id": task.id,
        "total": len(doc_ids),
        "job_type": req.job_type,
        "filter": req.filter,
        "status": "started",
    }


@router.post("/reprocess/pause/{task_id}")
def pause_reprocess(
    task_id: str,
    admin: User = Depends(require_admin),
):
    """Pause a running batch reprocess."""
    from app.tasks.batch_reprocess import set_paused

    set_paused(task_id, True)
    logger.info("Admin '%s' paused reprocess task %s", admin.username, task_id)
    return {"detail": "Reprocess paused", "task_id": task_id}


@router.post("/reprocess/resume/{task_id}")
def resume_reprocess(
    task_id: str,
    admin: User = Depends(require_admin),
):
    """Resume a paused batch reprocess."""
    from app.tasks.batch_reprocess import set_paused

    set_paused(task_id, False)
    logger.info("Admin '%s' resumed reprocess task %s", admin.username, task_id)
    return {"detail": "Reprocess resumed", "task_id": task_id}


@router.post("/reprocess/skip/{task_id}")
def skip_current_document(
    task_id: str,
    admin: User = Depends(require_admin),
):
    """Skip the current document being processed."""
    from app.tasks.batch_reprocess import set_skip

    set_skip(task_id)
    logger.info(
        "Admin '%s' skipped current document in task %s", admin.username, task_id
    )
    return {"detail": "Skipping current document", "task_id": task_id}


@router.post("/reprocess/cancel/{task_id}")
def cancel_reprocess(
    task_id: str,
    admin: User = Depends(require_admin),
):
    """Cancel a running batch reprocess."""
    from app.tasks.batch_reprocess import set_active_task, set_cancelled

    set_cancelled(task_id)
    # Clear active task immediately so UI unblocks (task will clean up on next iteration)
    set_active_task(None)
    logger.info("Admin '%s' cancelled reprocess task %s", admin.username, task_id)
    return {"detail": "Reprocess cancelled", "task_id": task_id}


@router.get("/reprocess/active")
def get_active_reprocess(
    admin: User = Depends(require_admin),
):
    """Check if a batch reprocess is currently running."""
    from app.tasks.batch_reprocess import get_active_task, is_paused

    task_id = get_active_task()
    if not task_id:
        return {"active": False}

    result = AsyncResult(task_id, app=celery_app)
    if result.state in ("SUCCESS", "FAILURE", "REVOKED"):
        # Stale key — clean it up
        from app.tasks.batch_reprocess import set_active_task

        set_active_task(None)
        return {"active": False}

    return {
        "active": True,
        "task_id": task_id,
        "paused": is_paused(task_id),
    }


@router.get("/reprocess/stats")
def reprocess_stats(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get document stats for reprocess filters."""
    total = (
        db.query(func.count(Document.id)).filter(Document.deleted_at.is_(None)).scalar()
    )
    no_text = (
        db.query(func.count(Document.id))
        .filter(
            Document.deleted_at.is_(None),
            (Document.content_text.is_(None)) | (Document.content_text == ""),
        )
        .scalar()
    )
    # Docs with text but no AI analysis (ready for AI)
    no_ai_ready = (
        db.query(func.count(Document.id))
        .filter(
            Document.deleted_at.is_(None),
            Document.ai_metadata.is_(None),
            Document.content_text.isnot(None),
            Document.content_text != "",
        )
        .scalar()
    )
    # Docs with no text AND no AI (need OCR first)
    no_ai_needs_ocr = (
        db.query(func.count(Document.id))
        .filter(
            Document.deleted_at.is_(None),
            Document.ai_metadata.is_(None),
            (Document.content_text.is_(None)) | (Document.content_text == ""),
        )
        .scalar()
    )
    with_text = total - no_text

    return {
        "total": total,
        "with_text": with_text,
        "no_text": no_text,
        "no_ai": no_ai_ready,
        "no_ai_needs_ocr": no_ai_needs_ocr,
    }

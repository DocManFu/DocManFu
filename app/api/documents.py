import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.deps import get_db
from app.models.document import Document
from app.models.processing_job import JobType, ProcessingJob
from app.models.tag import Tag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


# --- Response Models ---


class TagResponse(BaseModel):
    id: UUID
    name: str
    color: str

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    id: UUID
    filename: str
    original_name: str
    ai_generated_name: str | None
    document_type: str | None
    file_size: int
    upload_date: datetime
    processed_date: datetime | None
    tags: list[TagResponse]

    model_config = {"from_attributes": True}


class DocumentDetail(BaseModel):
    id: UUID
    filename: str
    original_name: str
    content_text: str | None
    ai_generated_name: str | None
    document_type: str | None
    ai_metadata: dict | None
    file_path: str
    mime_type: str
    file_size: int
    upload_date: datetime
    processed_date: datetime | None
    created_at: datetime
    updated_at: datetime
    tags: list[TagResponse]

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    documents: list[DocumentListItem]
    total: int
    offset: int
    limit: int


class UploadResponse(BaseModel):
    id: UUID
    filename: str
    original_name: str
    file_size: int
    upload_date: datetime
    job_id: UUID | None
    message: str


class DocumentUpdateRequest(BaseModel):
    original_name: str | None = None
    tags: list[str] | None = None  # Tag names — found or created


class ReprocessResponse(BaseModel):
    jobs: list[dict]
    message: str


# --- Helpers ---


def _get_document_or_404(db: Session, document_id: UUID) -> Document:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.deleted_at.is_(None))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# --- Endpoints ---
# NOTE: /search and /upload MUST be defined before /{document_id} routes


@router.get("/search", response_model=PaginatedResponse)
def search_documents(
    q: str = Query(..., min_length=1, description="Search query"),
    document_type: str | None = Query(None),
    tag: str | None = Query(None, description="Filter by tag name"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Search across document content, original names, and AI-generated names."""
    query = db.query(Document).filter(Document.deleted_at.is_(None))

    search_pattern = f"%{q}%"
    query = query.filter(
        or_(
            Document.content_text.ilike(search_pattern),
            Document.original_name.ilike(search_pattern),
            Document.ai_generated_name.ilike(search_pattern),
        )
    )

    if document_type:
        query = query.filter(Document.document_type == document_type)
    if tag:
        query = query.filter(Document.tags.any(Tag.name == tag))

    total = query.count()
    docs = (
        query.options(selectinload(Document.tags))
        .order_by(Document.upload_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return PaginatedResponse(documents=docs, total=total, offset=offset, limit=limit)


@router.post("/upload", response_model=UploadResponse, status_code=200)
async def upload_document(file: UploadFile, db: Session = Depends(get_db)):
    # Validate extension
    original_name = file.filename or "unknown.pdf"
    if not original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Validate MIME type
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Read file content and check size
    content = await file.read()
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB} MB",
        )

    # Build storage path: {UPLOAD_DIR}/YYYY/MM/DD/{uuid4}.pdf
    now = datetime.now(timezone.utc)
    file_uuid = uuid.uuid4()
    generated_filename = f"{file_uuid}.pdf"
    relative_dir = Path(now.strftime("%Y/%m/%d"))
    relative_path = relative_dir / generated_filename

    abs_dir = Path(settings.UPLOAD_DIR) / relative_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    abs_path = Path(settings.UPLOAD_DIR) / relative_path

    # Write file to disk
    abs_path.write_bytes(content)
    logger.info("Stored file %s (%d bytes) at %s", original_name, len(content), abs_path)

    # Create Document record
    doc = Document(
        filename=generated_filename,
        original_name=original_name,
        file_path=str(relative_path),
        mime_type="application/pdf",
        file_size=len(content),
        upload_date=now,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Create OCR processing job and dispatch to Celery
    job = ProcessingJob(document_id=doc.id, job_type=JobType.ocr)
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.tasks.ocr import process_ocr

    task = process_ocr.delay(str(job.id), str(doc.id))
    job.celery_task_id = task.id
    db.commit()

    logger.info("Dispatched OCR job %s (celery task %s) for document %s", job.id, task.id, doc.id)

    return UploadResponse(
        id=doc.id,
        filename=doc.filename,
        original_name=doc.original_name,
        file_size=doc.file_size,
        upload_date=doc.upload_date,
        job_id=job.id,
        message="Document uploaded successfully",
    )


@router.get("", response_model=PaginatedResponse)
def list_documents(
    document_type: str | None = Query(None, description="Filter by document type"),
    tag: str | None = Query(None, description="Filter by tag name"),
    date_from: datetime | None = Query(None, description="Filter from date (inclusive)"),
    date_to: datetime | None = Query(None, description="Filter to date (inclusive)"),
    sort_by: str = Query("upload_date", description="Sort field: upload_date, name, size, type"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List documents with filtering, sorting, and pagination."""
    query = db.query(Document).filter(Document.deleted_at.is_(None))

    if document_type:
        query = query.filter(Document.document_type == document_type)
    if tag:
        query = query.filter(Document.tags.any(Tag.name == tag))
    if date_from:
        query = query.filter(Document.upload_date >= date_from)
    if date_to:
        query = query.filter(Document.upload_date <= date_to)

    # Sorting
    sort_columns = {
        "upload_date": Document.upload_date,
        "name": Document.original_name,
        "size": Document.file_size,
        "type": Document.document_type,
    }
    sort_col = sort_columns.get(sort_by, Document.upload_date)
    query = query.order_by(sort_col.asc() if order == "asc" else sort_col.desc())

    total = query.count()
    docs = (
        query.options(selectinload(Document.tags))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return PaginatedResponse(documents=docs, total=total, offset=offset, limit=limit)


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: UUID, db: Session = Depends(get_db)):
    """Get a single document with full metadata and tags."""
    doc = (
        db.query(Document)
        .options(selectinload(Document.tags))
        .filter(Document.id == document_id, Document.deleted_at.is_(None))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.put("/{document_id}", response_model=DocumentDetail)
def update_document(
    document_id: UUID,
    update: DocumentUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update document name and/or tags."""
    doc = _get_document_or_404(db, document_id)

    if update.original_name is not None:
        doc.original_name = update.original_name

    if update.tags is not None:
        new_tags = []
        for tag_name in update.tags:
            tag = db.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                tag = Tag(name=tag_name, color="#6B7280")
                db.add(tag)
                db.flush()
            new_tags.append(tag)
        doc.tags = new_tags

    db.commit()

    # Re-fetch with tags eagerly loaded for response
    doc = (
        db.query(Document)
        .options(selectinload(Document.tags))
        .filter(Document.id == document_id)
        .first()
    )
    return doc


@router.delete("/{document_id}", status_code=200)
def delete_document(document_id: UUID, db: Session = Depends(get_db)):
    """Soft-delete a document."""
    doc = _get_document_or_404(db, document_id)
    doc.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "Document deleted"}


@router.get("/{document_id}/download")
def download_document(document_id: UUID, db: Session = Depends(get_db)):
    """Download the document file."""
    doc = _get_document_or_404(db, document_id)
    abs_path = Path(settings.UPLOAD_DIR) / doc.file_path
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Use AI name or user-edited name, slugified, with original extension
    display_name = doc.ai_generated_name or doc.original_name
    ext = Path(doc.original_name).suffix or ".pdf"
    stem = Path(display_name).stem
    slug = re.sub(r"[^\w\s-]", "", stem.lower()).strip()
    slug = re.sub(r"[\s]+", "_", slug)
    download_name = f"{slug}{ext}" if slug else doc.original_name

    return FileResponse(
        path=str(abs_path),
        filename=download_name,
        media_type=doc.mime_type,
    )


@router.post("/{document_id}/reprocess", response_model=ReprocessResponse)
def reprocess_document(document_id: UUID, db: Session = Depends(get_db)):
    """Trigger reprocessing (OCR followed by AI analysis if configured)."""
    doc = _get_document_or_404(db, document_id)

    abs_path = Path(settings.UPLOAD_DIR) / doc.file_path
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Create and dispatch OCR job (AI analysis auto-follows when OCR completes)
    ocr_job = ProcessingJob(document_id=doc.id, job_type=JobType.ocr)
    db.add(ocr_job)
    db.commit()
    db.refresh(ocr_job)

    from app.tasks.ocr import process_ocr

    task = process_ocr.delay(str(ocr_job.id), str(doc.id))
    ocr_job.celery_task_id = task.id
    db.commit()

    logger.info("Dispatched reprocess OCR job %s for document %s", ocr_job.id, doc.id)

    return ReprocessResponse(
        jobs=[{"job_id": str(ocr_job.id), "job_type": "ocr"}],
        message="Reprocessing started. OCR will run first, followed by AI analysis if configured.",
    )

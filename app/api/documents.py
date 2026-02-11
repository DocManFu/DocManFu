import csv
import io
import logging
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.search import update_search_vector
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
    bill_status: str | None = None
    bill_due_date: date | None = None
    bill_paid_at: datetime | None = None

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
    bill_status: str | None = None
    bill_due_date: date | None = None
    bill_paid_at: datetime | None = None

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    documents: list[DocumentListItem]
    total: int
    offset: int
    limit: int


class SearchResultItem(BaseModel):
    id: UUID
    filename: str
    original_name: str
    ai_generated_name: str | None
    document_type: str | None
    file_size: int
    upload_date: datetime
    processed_date: datetime | None
    tags: list[TagResponse]
    headline: str | None = None
    rank: float = 0.0

    model_config = {"from_attributes": True}


class SearchPaginatedResponse(BaseModel):
    documents: list[SearchResultItem]
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
    ai_generated_name: str | None = None
    document_type: str | None = None
    ai_metadata: dict | None = None


class ReprocessResponse(BaseModel):
    jobs: list[dict]
    message: str


class BulkTagRequest(BaseModel):
    document_ids: list[UUID]
    add_tags: list[str] = []
    remove_tags: list[str] = []


class BulkDeleteRequest(BaseModel):
    document_ids: list[UUID]


class BulkReprocessRequest(BaseModel):
    document_ids: list[UUID]


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


@router.get("/search", response_model=SearchPaginatedResponse)
def search_documents(
    q: str = Query(..., min_length=1, description="Search query"),
    document_type: str | None = Query(None),
    tag: str | None = Query(None, description="Filter by tag name"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Full-text search using PostgreSQL tsvector with ranking and highlights."""
    ts_query = func.plainto_tsquery("english", q)

    # Base filter: not deleted, matches search query
    query = (
        db.query(
            Document,
            func.ts_rank(Document.search_vector, ts_query).label("rank"),
            func.ts_headline(
                "english",
                func.coalesce(Document.content_text, ""),
                ts_query,
                "MaxWords=35, MinWords=15, StartSel=<mark>, StopSel=</mark>",
            ).label("headline"),
        )
        .filter(Document.deleted_at.is_(None))
        .filter(Document.search_vector.op("@@")(ts_query))
    )

    if document_type:
        query = query.filter(Document.document_type == document_type)
    if tag:
        query = query.filter(Document.tags.any(Tag.name == tag))

    total = query.count()
    rows = (
        query.options(selectinload(Document.tags))
        .order_by(text("rank DESC"))
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []
    for doc, rank, headline in rows:
        item = SearchResultItem.model_validate(doc)
        item.rank = float(rank)
        item.headline = headline
        results.append(item)

    return SearchPaginatedResponse(
        documents=results, total=total, offset=offset, limit=limit
    )


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

    update_search_vector(db, doc.id)

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


# --- Bulk Operations ---
# NOTE: These must be defined BEFORE /{document_id} to avoid path conflicts


@router.post("/bulk/tag", status_code=200)
def bulk_tag_documents(req: BulkTagRequest, db: Session = Depends(get_db)):
    """Add or remove tags on multiple documents."""
    docs = (
        db.query(Document)
        .options(selectinload(Document.tags))
        .filter(Document.id.in_(req.document_ids), Document.deleted_at.is_(None))
        .all()
    )

    # Resolve/create tags to add
    tags_to_add = []
    for tag_name in req.add_tags:
        tag = db.query(Tag).filter(Tag.name == tag_name).first()
        if not tag:
            tag = Tag(name=tag_name, color="#6B7280")
            db.add(tag)
            db.flush()
        tags_to_add.append(tag)

    for doc in docs:
        for tag in tags_to_add:
            if tag not in doc.tags:
                doc.tags.append(tag)
        for tag_name in req.remove_tags:
            doc.tags = [t for t in doc.tags if t.name != tag_name]

    db.commit()
    return {"detail": f"Updated tags on {len(docs)} documents"}


@router.post("/bulk/delete", status_code=200)
def bulk_delete_documents(req: BulkDeleteRequest, db: Session = Depends(get_db)):
    """Soft-delete multiple documents."""
    now = datetime.now(timezone.utc)
    count = (
        db.query(Document)
        .filter(Document.id.in_(req.document_ids), Document.deleted_at.is_(None))
        .update({Document.deleted_at: now}, synchronize_session="fetch")
    )
    db.commit()
    return {"detail": f"Deleted {count} documents"}


@router.post("/bulk/reprocess", status_code=200)
def bulk_reprocess_documents(req: BulkReprocessRequest, db: Session = Depends(get_db)):
    """Create OCR jobs for multiple documents."""
    docs = (
        db.query(Document)
        .filter(Document.id.in_(req.document_ids), Document.deleted_at.is_(None))
        .all()
    )

    jobs = []
    for doc in docs:
        abs_path = Path(settings.UPLOAD_DIR) / doc.file_path
        if not abs_path.exists():
            continue

        ocr_job = ProcessingJob(document_id=doc.id, job_type=JobType.ocr)
        db.add(ocr_job)
        db.flush()

        from app.tasks.ocr import process_ocr

        task = process_ocr.delay(str(ocr_job.id), str(doc.id))
        ocr_job.celery_task_id = task.id
        jobs.append({"job_id": str(ocr_job.id), "document_id": str(doc.id)})

    db.commit()
    return {"detail": f"Started reprocessing {len(jobs)} documents", "jobs": jobs}


@router.get("/export/csv")
def export_documents_csv(
    document_type: str | None = Query(None),
    tag: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: Session = Depends(get_db),
):
    """Export document metadata as CSV."""
    query = db.query(Document).filter(Document.deleted_at.is_(None))

    if document_type:
        query = query.filter(Document.document_type == document_type)
    if tag:
        query = query.filter(Document.tags.any(Tag.name == tag))
    if date_from:
        query = query.filter(Document.upload_date >= date_from)
    if date_to:
        query = query.filter(Document.upload_date <= date_to)

    docs = query.options(selectinload(Document.tags)).order_by(Document.upload_date.desc()).all()

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "original_name", "ai_generated_name", "document_type",
            "file_size", "upload_date", "processed_date", "tags",
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for doc in docs:
            writer.writerow([
                str(doc.id),
                doc.original_name,
                doc.ai_generated_name or "",
                doc.document_type or "",
                doc.file_size,
                doc.upload_date.isoformat() if doc.upload_date else "",
                doc.processed_date.isoformat() if doc.processed_date else "",
                "; ".join(t.name for t in doc.tags),
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=documents.csv"},
    )


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
    """Update document name, tags, and/or AI-generated fields."""
    doc = _get_document_or_404(db, document_id)

    search_dirty = False
    if update.original_name is not None:
        doc.original_name = update.original_name
        search_dirty = True

    if update.ai_generated_name is not None:
        doc.ai_generated_name = update.ai_generated_name
        search_dirty = True

    if update.document_type is not None:
        old_type = doc.document_type
        doc.document_type = update.document_type

        # Bill tracking side effects
        if update.document_type in ("bill", "invoice"):
            if doc.bill_status not in ("paid", "dismissed"):
                doc.bill_status = "unpaid"
            # Parse due_date from ai_metadata (use updated or existing)
            meta = update.ai_metadata if update.ai_metadata is not None else (doc.ai_metadata or {})
            raw_due = meta.get("due_date")
            if raw_due:
                try:
                    doc.bill_due_date = date.fromisoformat(raw_due)
                except (ValueError, TypeError):
                    pass
        elif old_type in ("bill", "invoice") and update.document_type not in ("bill", "invoice"):
            # Changed away from bill — clear bill fields
            doc.bill_status = None
            doc.bill_due_date = None
            doc.bill_paid_at = None

    if update.ai_metadata is not None:
        doc.ai_metadata = update.ai_metadata
        search_dirty = True

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

    if search_dirty:
        update_search_vector(db, document_id)

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

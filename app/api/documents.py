import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.deps import get_db
from app.models.document import Document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


class UploadResponse(BaseModel):
    id: UUID
    filename: str
    original_name: str
    file_size: int
    upload_date: datetime
    message: str


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

    return UploadResponse(
        id=doc.id,
        filename=doc.filename,
        original_name=doc.original_name,
        file_size=doc.file_size,
        upload_date=doc.upload_date,
        message="Document uploaded successfully",
    )

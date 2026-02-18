"""Job status API – track background processing jobs."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.celery_app import celery_app
from app.core.events import publish_event
from app.db.deps import get_db
from app.models.document import Document
from app.models.processing_job import JobStatus, JobType, ProcessingJob
from app.models.user import User

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobStatusResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    job_type: str
    status: str
    progress: int
    error_message: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    result_data: dict | None

    model_config = {"from_attributes": True}


class JobListItem(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    job_type: str
    status: str
    progress: int
    error_message: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    result_data: dict | None
    document_name: str


class JobListResponse(BaseModel):
    jobs: list[JobListItem]
    total: int
    offset: int
    limit: int


@router.get("", response_model=JobListResponse)
def list_jobs(
    status: str | None = None,
    job_type: str | None = None,
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all processing jobs with filtering and pagination."""
    query = db.query(ProcessingJob).join(Document).filter(Document.deleted_at.is_(None))

    if user.role != "admin":
        query = query.filter(Document.user_id == user.id)

    if status:
        try:
            query = query.filter(ProcessingJob.status == JobStatus(status))
        except ValueError:
            pass

    if job_type:
        try:
            query = query.filter(ProcessingJob.job_type == JobType(job_type))
        except ValueError:
            pass

    total = query.count()

    if sort_order == "asc":
        order = ProcessingJob.created_at.asc()
    else:
        order = ProcessingJob.created_at.desc()
    jobs = query.order_by(order).offset(offset).limit(limit).all()

    return JobListResponse(
        jobs=[
            JobListItem(
                id=j.id,
                document_id=j.document_id,
                job_type=j.job_type.value,
                status=j.status.value,
                progress=j.progress,
                error_message=j.error_message,
                created_at=j.created_at.isoformat(),
                started_at=j.started_at.isoformat() if j.started_at else None,
                completed_at=j.completed_at.isoformat() if j.completed_at else None,
                result_data=j.result_data,
                document_name=j.document.ai_generated_name or j.document.original_name,
            )
            for j in jobs
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/by-document/{document_id}", response_model=list[JobStatusResponse])
def get_document_jobs(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get active (pending/processing) jobs for a document."""
    # Verify ownership
    doc_query = db.query(Document).filter(
        Document.id == document_id, Document.deleted_at.is_(None)
    )
    if user.role != "admin":
        doc_query = doc_query.filter(Document.user_id == user.id)
    if not doc_query.first():
        raise HTTPException(status_code=404, detail="Document not found")

    jobs = (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.document_id == document_id,
            ProcessingJob.status.in_([JobStatus.pending, JobStatus.processing]),
        )
        .order_by(ProcessingJob.created_at)
        .all()
    )
    return [
        JobStatusResponse(
            id=j.id,
            document_id=j.document_id,
            job_type=j.job_type.value,
            status=j.status.value,
            progress=j.progress,
            error_message=j.error_message,
            created_at=j.created_at.isoformat(),
            started_at=j.started_at.isoformat() if j.started_at else None,
            completed_at=j.completed_at.isoformat() if j.completed_at else None,
            result_data=j.result_data,
        )
        for j in jobs
    ]


@router.get(
    "/by-document/{document_id}/history", response_model=list[JobStatusResponse]
)
def get_document_job_history(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all processing jobs for a document (including completed/failed)."""
    doc_query = db.query(Document).filter(
        Document.id == document_id, Document.deleted_at.is_(None)
    )
    if user.role != "admin":
        doc_query = doc_query.filter(Document.user_id == user.id)
    if not doc_query.first():
        raise HTTPException(status_code=404, detail="Document not found")

    jobs = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.document_id == document_id)
        .order_by(ProcessingJob.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        JobStatusResponse(
            id=j.id,
            document_id=j.document_id,
            job_type=j.job_type.value,
            status=j.status.value,
            progress=j.progress,
            error_message=j.error_message,
            created_at=j.created_at.isoformat(),
            started_at=j.started_at.isoformat() if j.started_at else None,
            completed_at=j.completed_at.isoformat() if j.completed_at else None,
            result_data=j.result_data,
        )
        for j in jobs
    ]


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the current status and progress of a processing job."""
    job = db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify ownership via the job's document
    if user.role != "admin":
        doc = db.get(Document, job.document_id)
        if not doc or doc.user_id != user.id:
            raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        id=job.id,
        document_id=job.document_id,
        job_type=job.job_type.value,
        status=job.status.value,
        progress=job.progress,
        error_message=job.error_message,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        result_data=job.result_data,
    )


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cancel a pending or processing job."""
    job = db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify ownership via the job's document
    doc = db.get(Document, job.document_id)
    if user.role != "admin":
        if not doc or doc.user_id != user.id:
            raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in (JobStatus.pending, JobStatus.processing):
        raise HTTPException(
            status_code=400,
            detail="Job cannot be cancelled in its current state",
        )

    # Revoke the Celery task if it has one
    if job.celery_task_id:
        celery_app.control.revoke(job.celery_task_id, terminate=True, signal="SIGTERM")

    job.status = JobStatus.failed
    job.error_message = "Cancelled by user"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()

    # Publish SSE event
    user_id = str(doc.user_id) if doc and doc.user_id else None
    publish_event(
        "job.failed",
        {
            "job_id": str(job.id),
            "document_id": str(job.document_id),
            "job_type": job.job_type.value,
            "status": "failed",
            "progress": job.progress,
            "error_message": "Cancelled by user",
            "user_id": user_id,
        },
    )

    return {"detail": "Job cancelled"}

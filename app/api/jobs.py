"""Job status API – track background processing jobs."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.models.processing_job import JobStatus, ProcessingJob

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


@router.get("/by-document/{document_id}", response_model=list[JobStatusResponse])
def get_document_jobs(document_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get active (pending/processing) jobs for a document."""
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


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(job_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get the current status and progress of a processing job."""
    job = db.get(ProcessingJob, job_id)
    if job is None:
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

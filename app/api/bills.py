"""Bills inbox API — lifecycle tracking for bill-type documents."""

import logging
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import nulls_last
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_write_access
from app.db.deps import get_db
from app.models.document import Document
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bills", tags=["bills"])


# --- Response Models ---


class BillListItem(BaseModel):
    id: UUID
    filename: str
    original_name: str
    ai_generated_name: str | None
    document_type: str | None
    file_size: int
    upload_date: datetime
    bill_status: str | None
    bill_due_date: date | None
    bill_paid_at: datetime | None
    ai_metadata: dict | None

    model_config = {"from_attributes": True}


class BillsListResponse(BaseModel):
    bills: list[BillListItem]
    total: int
    offset: int
    limit: int


class BillStatusUpdate(BaseModel):
    status: str  # "paid", "dismissed", "unpaid"


class BillDueDateUpdate(BaseModel):
    due_date: date | None = None


# --- Endpoints ---


@router.get("", response_model=BillsListResponse)
def list_bills(
    status: str = Query(
        "unpaid", description="Filter by bill status: unpaid, paid, dismissed, all"
    ),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List bills filtered by status, sorted by due date (nulls last)."""
    query = db.query(Document).filter(
        Document.deleted_at.is_(None),
        Document.bill_status.isnot(None),
    )

    if user.role != "admin":
        query = query.filter(Document.user_id == user.id)

    if status != "all":
        query = query.filter(Document.bill_status == status)

    total = query.count()
    bills = (
        query.order_by(
            nulls_last(Document.bill_due_date.asc()), Document.upload_date.desc()
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return BillsListResponse(bills=bills, total=total, offset=offset, limit=limit)


@router.patch("/{bill_id}/status")
def update_bill_status(
    bill_id: UUID,
    body: BillStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_write_access),
):
    """Set bill status to paid, dismissed, or unpaid."""
    if body.status not in ("paid", "dismissed", "unpaid"):
        raise HTTPException(
            status_code=400, detail="Status must be 'paid', 'dismissed', or 'unpaid'"
        )

    query = db.query(Document).filter(
        Document.id == bill_id, Document.deleted_at.is_(None)
    )
    if user.role != "admin":
        query = query.filter(Document.user_id == user.id)
    doc = query.first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.bill_status = body.status

    if body.status == "paid":
        doc.bill_paid_at = datetime.now(timezone.utc)
    elif body.status == "unpaid":
        doc.bill_paid_at = None

    db.commit()

    return {
        "detail": f"Bill status updated to '{body.status}'",
        "bill_status": doc.bill_status,
        "bill_paid_at": doc.bill_paid_at.isoformat() if doc.bill_paid_at else None,
    }


@router.patch("/{bill_id}/due-date")
def update_bill_due_date(
    bill_id: UUID,
    body: BillDueDateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_write_access),
):
    """Manually set or clear the due date for a bill."""
    query = db.query(Document).filter(
        Document.id == bill_id, Document.deleted_at.is_(None)
    )
    if user.role != "admin":
        query = query.filter(Document.user_id == user.id)
    doc = query.first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.bill_due_date = body.due_date
    db.commit()

    return {
        "detail": "Due date updated",
        "bill_due_date": doc.bill_due_date.isoformat() if doc.bill_due_date else None,
    }

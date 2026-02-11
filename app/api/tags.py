import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.models.tag import Tag, document_tags

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tags", tags=["tags"])


# --- Response / Request Models ---


class TagWithCount(BaseModel):
    id: UUID
    name: str
    color: str
    document_count: int

    model_config = {"from_attributes": True}


class TagCreateRequest(BaseModel):
    name: str
    color: str = "#6B7280"


class TagUpdateRequest(BaseModel):
    name: str | None = None
    color: str | None = None


class TagMergeRequest(BaseModel):
    source_tag_ids: list[UUID]
    target_tag_id: UUID


class TagResponse(BaseModel):
    id: UUID
    name: str
    color: str

    model_config = {"from_attributes": True}


# --- Endpoints ---


@router.get("", response_model=list[TagWithCount])
def list_tags(db: Session = Depends(get_db)):
    """List all tags with their document counts."""
    rows = (
        db.query(
            Tag.id,
            Tag.name,
            Tag.color,
            func.count(document_tags.c.document_id).label("document_count"),
        )
        .outerjoin(document_tags, Tag.id == document_tags.c.tag_id)
        .group_by(Tag.id)
        .order_by(Tag.name)
        .all()
    )
    return [
        TagWithCount(id=r.id, name=r.name, color=r.color, document_count=r.document_count)
        for r in rows
    ]


@router.post("", response_model=TagResponse, status_code=201)
def create_tag(req: TagCreateRequest, db: Session = Depends(get_db)):
    """Create a new tag."""
    existing = db.query(Tag).filter(Tag.name == req.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Tag already exists")

    tag = Tag(name=req.name, color=req.color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.put("/{tag_id}", response_model=TagResponse)
def update_tag(tag_id: UUID, req: TagUpdateRequest, db: Session = Depends(get_db)):
    """Update a tag's name or color."""
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    if req.name is not None and req.name != tag.name:
        conflict = db.query(Tag).filter(Tag.name == req.name).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Tag name already in use")
        tag.name = req.name

    if req.color is not None:
        tag.color = req.color

    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=200)
def delete_tag(tag_id: UUID, db: Session = Depends(get_db)):
    """Delete a tag and remove all associations."""
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Remove associations
    db.execute(document_tags.delete().where(document_tags.c.tag_id == tag_id))
    db.delete(tag)
    db.commit()
    return {"detail": "Tag deleted"}


@router.post("/merge", status_code=200)
def merge_tags(req: TagMergeRequest, db: Session = Depends(get_db)):
    """Merge source tags into a target tag. Moves associations and deletes sources."""
    target = db.get(Tag, req.target_tag_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target tag not found")

    for source_id in req.source_tag_ids:
        if source_id == req.target_tag_id:
            continue
        source = db.get(Tag, source_id)
        if not source:
            continue

        # Get document IDs already associated with target
        existing = set(
            r[0]
            for r in db.execute(
                document_tags.select().where(document_tags.c.tag_id == req.target_tag_id)
            ).fetchall()
        )

        # Move associations from source to target (skip duplicates)
        source_docs = db.execute(
            document_tags.select().where(document_tags.c.tag_id == source_id)
        ).fetchall()

        for row in source_docs:
            doc_id = row[0]
            if doc_id not in existing:
                db.execute(
                    document_tags.insert().values(
                        document_id=doc_id, tag_id=req.target_tag_id
                    )
                )

        # Remove source associations and delete source tag
        db.execute(document_tags.delete().where(document_tags.c.tag_id == source_id))
        db.delete(source)

    db.commit()
    return {"detail": f"Merged {len(req.source_tag_ids)} tags into '{target.name}'"}

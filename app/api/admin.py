"""Admin API — user management (admin-only)."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.core.security import hash_password
from app.db.deps import get_db
from app.models.document import Document
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- Schemas ---


class CreateUserRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "user"  # admin, user, readonly


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str


class AdminUserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    role: str
    is_active: bool
    has_api_key: bool
    document_count: int
    created_at: str


# --- Endpoints ---


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all users with document counts."""
    rows = (
        db.query(
            User,
            func.count(Document.id).label("document_count"),
        )
        .outerjoin(
            Document, (Document.user_id == User.id) & Document.deleted_at.is_(None)
        )
        .group_by(User.id)
        .order_by(User.created_at)
        .all()
    )
    return [
        AdminUserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            has_api_key=user.api_key is not None,
            document_count=doc_count,
            created_at=user.created_at.isoformat(),
        )
        for user, doc_count in rows
    ]


@router.post("/users", response_model=AdminUserResponse, status_code=201)
def create_user(
    req: CreateUserRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new user (admin-only, invite-only registration)."""
    if req.role not in ("admin", "user", "readonly"):
        raise HTTPException(
            status_code=400, detail="Role must be admin, user, or readonly"
        )
    if len(req.password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )

    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=409, detail="Email already in use")

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        role=req.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(
        "Admin '%s' created user '%s' with role '%s'",
        admin.username,
        user.username,
        user.role,
    )

    return AdminUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        has_api_key=False,
        document_count=0,
        created_at=user.created_at.isoformat(),
    )


@router.put("/users/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: UUID,
    req: UpdateUserRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a user's role or active status."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if req.role is not None:
        if req.role not in ("admin", "user", "readonly"):
            raise HTTPException(
                status_code=400, detail="Role must be admin, user, or readonly"
            )
        # Prevent removing last admin
        if user.role == "admin" and req.role != "admin":
            admin_count = (
                db.query(User)
                .filter(User.role == "admin", User.is_active)
                .count()
            )
            if admin_count <= 1:
                raise HTTPException(
                    status_code=400, detail="Cannot remove the last admin"
                )
        user.role = req.role

    if req.is_active is not None:
        if not req.is_active:
            # Can't deactivate yourself
            if user.id == admin.id:
                raise HTTPException(
                    status_code=400, detail="Cannot deactivate yourself"
                )
            # Can't deactivate last admin
            if user.role == "admin":
                admin_count = (
                    db.query(User)
                    .filter(User.role == "admin", User.is_active)
                    .count()
                )
                if admin_count <= 1:
                    raise HTTPException(
                        status_code=400, detail="Cannot deactivate the last admin"
                    )
        user.is_active = req.is_active

    db.commit()
    db.refresh(user)

    doc_count = (
        db.query(Document)
        .filter(Document.user_id == user.id, Document.deleted_at.is_(None))
        .count()
    )

    return AdminUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        has_api_key=user.api_key is not None,
        document_count=doc_count,
        created_at=user.created_at.isoformat(),
    )


@router.delete("/users/{user_id}", status_code=200)
def deactivate_user(
    user_id: UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deactivate a user (sets is_active=False)."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    if user.role == "admin":
        admin_count = (
            db.query(User).filter(User.role == "admin", User.is_active).count()
        )
        if admin_count <= 1:
            raise HTTPException(
                status_code=400, detail="Cannot deactivate the last admin"
            )

    user.is_active = False
    db.commit()

    logger.info("Admin '%s' deactivated user '%s'", admin.username, user.username)
    return {"detail": f"User '{user.username}' deactivated"}


@router.post("/users/{user_id}/reset-password", status_code=200)
def reset_user_password(
    user_id: UUID,
    req: ResetPasswordRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reset a user's password (admin-only)."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if len(req.new_password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )

    user.hashed_password = hash_password(req.new_password)
    db.commit()

    logger.info(
        "Admin '%s' reset password for user '%s'", admin.username, user.username
    )
    return {"detail": f"Password reset for user '{user.username}'"}

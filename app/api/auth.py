"""Authentication API — login, setup, token refresh, API keys."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    hash_password,
    verify_password,
)
from app.db.deps import get_db
from app.models.document import Document
from app.models.tag import Tag
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --- Schemas ---


class SetupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username: str  # accepts username or email
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    role: str
    is_active: bool
    has_api_key: bool
    created_at: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class ApiKeyResponse(BaseModel):
    api_key: str


class SetupStatusResponse(BaseModel):
    setup_needed: bool


# --- Helpers ---


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        has_api_key=user.api_key is not None,
        created_at=user.created_at.isoformat(),
    )


def _token_response(user: User) -> TokenResponse:
    access_token = create_access_token(str(user.id), user.role)
    refresh_token = create_refresh_token(str(user.id))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_response(user),
    )


# --- Endpoints ---


@router.get("/setup-status", response_model=SetupStatusResponse)
def get_setup_status(db: Session = Depends(get_db)):
    """Check if initial setup (admin account creation) is needed."""
    user_count = db.query(User).count()
    return SetupStatusResponse(setup_needed=user_count == 0)


@router.post("/setup", response_model=TokenResponse)
def setup_admin(req: SetupRequest, db: Session = Depends(get_db)):
    """Create the first admin user. Only works when no users exist."""
    user_count = db.query(User).count()
    if user_count > 0:
        raise HTTPException(status_code=400, detail="Setup already completed")

    if not settings.JWT_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="JWT_SECRET_KEY must be set before creating users",
        )

    if len(req.password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.flush()

    # Backfill: assign all existing documents and tags to the new admin
    db.query(Document).filter(Document.user_id.is_(None)).update(
        {Document.user_id: user.id}, synchronize_session=False
    )
    db.query(Tag).filter(Tag.user_id.is_(None)).update(
        {Tag.user_id: user.id}, synchronize_session=False
    )
    db.commit()

    logger.info(
        "Admin user '%s' created during setup, existing data assigned", user.username
    )
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with username/email and password."""
    user = (
        db.query(User)
        .filter(or_(User.username == req.username, User.email == req.username))
        .first()
    )
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account is inactive")

    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(req: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a refresh token for new access + refresh tokens."""
    payload = decode_token(req.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return _token_response(user)


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    """Get the current authenticated user."""
    return _user_response(user)


@router.post("/api-key", response_model=ApiKeyResponse)
def create_api_key(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a new API key for the current user. Replaces any existing key."""
    key = generate_api_key()
    user.api_key = key
    db.commit()
    return ApiKeyResponse(api_key=key)


@router.delete("/api-key", status_code=200)
def revoke_api_key(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the current user's API key."""
    user.api_key = None
    db.commit()
    return {"detail": "API key revoked"}


@router.post("/change-password", status_code=200)
def change_password(
    req: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the current user's password."""
    if not verify_password(req.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(req.new_password) < 8:
        raise HTTPException(
            status_code=400, detail="New password must be at least 8 characters"
        )

    user.hashed_password = hash_password(req.new_password)
    db.commit()
    return {"detail": "Password changed"}

"""FastAPI dependencies for authentication and authorization."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.deps import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the current user from a Bearer token.

    Supports both JWT access tokens and API keys (prefixed with ``dmf_``).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # API key auth
    if token.startswith("dmf_"):
        user = db.query(User).filter(User.api_key == token).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive",
            )
        return user

    # JWT auth
    return user_from_token(token, "access", db)


def user_from_token(token: str, token_type: str, db: Session) -> User:
    """Validate a JWT of the given type and return its active user.

    Rejects tokens issued before the user's last password change.
    """
    payload = decode_token(token)
    if payload is None or payload.get("type") != token_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, payload["sub"])
    if not user or not user.is_active or payload.get("ver") != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def revoke_tokens(db: Session, user: User) -> int:
    """Invalidate all of the user's JWTs and return the new token_version.

    Incremented atomically in SQL so concurrent resets each get a distinct version.
    """
    return db.execute(
        update(User)
        .where(User.id == user.id)
        .values(token_version=User.token_version + 1)
        .returning(User.token_version)
    ).scalar_one()


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require the current user to have the admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def require_write_access(user: User = Depends(get_current_user)) -> User:
    """Require the current user to have write access (admin or user role)."""
    if user.role == "readonly":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access required",
        )
    return user

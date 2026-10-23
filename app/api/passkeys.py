"""Passkey (WebAuthn) API — register, list, and remove passkeys; sign in with one."""

import json
import logging
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.api.auth import TokenResponse, _token_response
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.events import get_redis_client
from app.core.security import verify_password
from app.db.deps import get_db
from app.models.passkey import Passkey
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/passkeys", tags=["passkeys"])

CHALLENGE_TTL_SECONDS = 300
CHALLENGE_KEY = "docmanfu:webauthn:{}"


# --- Schemas ---


class OptionsResponse(BaseModel):
    challenge_id: str
    options: dict


class RegisterOptionsRequest(BaseModel):
    password: str


class RegisterVerifyRequest(BaseModel):
    challenge_id: str
    credential: dict
    name: str = Field(default="Passkey", min_length=1, max_length=100)


class LoginVerifyRequest(BaseModel):
    challenge_id: str
    credential: dict


class PasskeyResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


# --- Helpers ---


def _rp() -> tuple[str, str]:
    """Return (rp_id, origin), or 400 if passkeys aren't configured."""
    if not settings.WEBAUTHN_ORIGIN:
        raise HTTPException(status_code=400, detail="Passkeys are not enabled")
    origin = settings.WEBAUTHN_ORIGIN.rstrip("/")
    return urlparse(origin).hostname, origin


def _store_challenge(purpose: str, challenge: bytes, user_id: str | None) -> str:
    challenge_id = secrets.token_urlsafe(32)
    data = {
        "purpose": purpose,
        "challenge": bytes_to_base64url(challenge),
        "user_id": user_id,
    }
    client = get_redis_client()
    try:
        client.set(
            CHALLENGE_KEY.format(challenge_id),
            json.dumps(data),
            ex=CHALLENGE_TTL_SECONDS,
        )
    finally:
        client.close()
    return challenge_id


def _pop_challenge(challenge_id: str, purpose: str) -> dict:
    """Fetch and delete a challenge so each one can be used only once."""
    client = get_redis_client()
    try:
        raw = client.getdel(CHALLENGE_KEY.format(challenge_id))
    finally:
        client.close()
    data = json.loads(raw) if raw else None
    if not data or data["purpose"] != purpose:
        raise HTTPException(
            status_code=400, detail="Passkey request expired, try again"
        )
    return data


# --- Registration (signed-in user) ---


@router.post("/register/options", response_model=OptionsResponse)
def registration_options(
    req: RegisterOptionsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start registering a new passkey for the current user.

    Requires the account password, so a stolen access token alone can't be
    turned into a permanent passkey login.
    """
    rp_id, _ = _rp()
    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=settings.APP_NAME,
        user_id=user.id.bytes,
        user_name=user.username,
        user_display_name=user.username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=pk.credential_id) for pk in user.passkeys
        ],
    )
    challenge_id = _store_challenge("register", options.challenge, str(user.id))
    return OptionsResponse(
        challenge_id=challenge_id, options=json.loads(options_to_json(options))
    )


@router.post("/register/verify", response_model=PasskeyResponse, status_code=201)
def registration_verify(
    req: RegisterVerifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Finish registering a passkey with the authenticator's response."""
    rp_id, origin = _rp()
    challenge = _pop_challenge(req.challenge_id, "register")
    if challenge["user_id"] != str(user.id):
        raise HTTPException(
            status_code=400, detail="Passkey request expired, try again"
        )

    try:
        verified = verify_registration_response(
            credential=req.credential,
            expected_challenge=base64url_to_bytes(challenge["challenge"]),
            expected_rp_id=rp_id,
            expected_origin=origin,
            require_user_verification=True,
        )
    except WebAuthnException as e:
        logger.info("Passkey registration failed for '%s': %s", user.username, e)
        raise HTTPException(status_code=400, detail="Passkey registration failed")

    if (
        db.query(Passkey)
        .filter(Passkey.credential_id == verified.credential_id)
        .first()
    ):
        raise HTTPException(
            status_code=400, detail="This passkey is already registered"
        )

    transports = req.credential.get("response", {}).get("transports")
    passkey = Passkey(
        user_id=user.id,
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=transports if isinstance(transports, list) else None,
        name=req.name.strip() or "Passkey",
    )
    db.add(passkey)
    db.commit()
    db.refresh(passkey)
    logger.info("Passkey '%s' registered for '%s'", passkey.name, user.username)
    return passkey


# --- Management ---


@router.get("", response_model=list[PasskeyResponse])
def list_passkeys(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List the current user's passkeys."""
    return (
        db.query(Passkey)
        .filter(Passkey.user_id == user.id)
        .order_by(Passkey.created_at)
        .all()
    )


@router.delete("/{passkey_id}")
def delete_passkey(
    passkey_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove one of the current user's passkeys."""
    passkey = (
        db.query(Passkey)
        .filter(Passkey.id == passkey_id, Passkey.user_id == user.id)
        .first()
    )
    if not passkey:
        raise HTTPException(status_code=404, detail="Passkey not found")
    db.delete(passkey)
    db.commit()
    return {"detail": "Passkey removed"}


# --- Sign in (public) ---


@router.post("/login/options", response_model=OptionsResponse)
def login_options():
    """Start a passkey sign-in. No username needed (discoverable credentials)."""
    rp_id, _ = _rp()
    options = generate_authentication_options(
        rp_id=rp_id, user_verification=UserVerificationRequirement.REQUIRED
    )
    challenge_id = _store_challenge("login", options.challenge, None)
    return OptionsResponse(
        challenge_id=challenge_id, options=json.loads(options_to_json(options))
    )


@router.post("/login/verify", response_model=TokenResponse)
def login_verify(req: LoginVerifyRequest, db: Session = Depends(get_db)):
    """Finish a passkey sign-in and issue tokens."""
    rp_id, origin = _rp()
    challenge = _pop_challenge(req.challenge_id, "login")

    failed = HTTPException(status_code=401, detail="Passkey sign-in failed")
    try:
        credential_id = base64url_to_bytes(req.credential["rawId"])
    except (KeyError, TypeError, ValueError):
        raise failed

    # Row lock serializes concurrent sign-ins so the sign count can't regress
    passkey = (
        db.query(Passkey)
        .filter(Passkey.credential_id == credential_id)
        .with_for_update()
        .first()
    )
    if not passkey:
        raise failed

    try:
        verified = verify_authentication_response(
            credential=req.credential,
            expected_challenge=base64url_to_bytes(challenge["challenge"]),
            expected_rp_id=rp_id,
            expected_origin=origin,
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except WebAuthnException as e:
        logger.info("Passkey sign-in failed: %s", e)
        raise failed

    user = passkey.owner
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account is inactive")

    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return _token_response(user)

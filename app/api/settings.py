"""Admin API — AI settings management."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.core.settings_service import (
    delete_all_ai_settings,
    get_all_ai_settings,
    get_ai_config,
    set_ai_settings,
)
from app.db.deps import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/settings", tags=["settings"])

_VALID_PROVIDERS = {"none", "openai", "anthropic", "ollama"}


# --- Schemas ---


class AISettingsUpdate(BaseModel):
    ai_provider: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None
    ai_base_url: str | None = None
    ai_max_text_length: int | None = None
    ai_timeout: int | None = None
    ai_max_pages: int | None = None
    ai_vision_dpi: int | None = None
    ai_vision_model: str | None = None


class TestConnectionRequest(BaseModel):
    ai_provider: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None
    ai_base_url: str | None = None
    ai_timeout: int | None = None


# --- Endpoints ---


@router.get("/ai")
def get_ai_settings(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return all AI settings with masked secrets and source indicators."""
    return get_all_ai_settings(db)


@router.put("/ai")
def update_ai_settings(
    req: AISettingsUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Partial update of AI settings."""
    data = req.model_dump(exclude_none=True)

    if "ai_provider" in data and data["ai_provider"] not in _VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider. Must be one of: {', '.join(sorted(_VALID_PROVIDERS))}",
        )

    if "ai_max_text_length" in data and data["ai_max_text_length"] < 100:
        raise HTTPException(status_code=400, detail="ai_max_text_length must be at least 100")

    if "ai_timeout" in data and data["ai_timeout"] < 5:
        raise HTTPException(status_code=400, detail="ai_timeout must be at least 5 seconds")

    if "ai_max_pages" in data and data["ai_max_pages"] < 1:
        raise HTTPException(status_code=400, detail="ai_max_pages must be at least 1")

    if "ai_vision_dpi" in data and data["ai_vision_dpi"] < 72:
        raise HTTPException(status_code=400, detail="ai_vision_dpi must be at least 72")

    set_ai_settings(db, data)
    logger.info("Admin '%s' updated AI settings", admin.username)
    return get_all_ai_settings(db)


@router.post("/ai/test")
def test_ai_connection(
    req: TestConnectionRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Test AI provider connection with the given or saved settings."""
    # Build config: start from saved, overlay with request values
    config = get_ai_config(db)
    overrides = req.model_dump(exclude_none=True)
    # Don't overlay masked keys
    for k, v in overrides.items():
        if k == "ai_api_key" and v.startswith("****"):
            continue
        config[k] = str(v) if not isinstance(v, str) else v

    provider = (config.get("ai_provider") or "none").lower()

    if provider == "none":
        raise HTTPException(status_code=400, detail="AI provider is set to 'none'")

    if provider not in ("openai", "anthropic", "ollama"):
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    if provider != "ollama" and not config.get("ai_api_key"):
        raise HTTPException(status_code=400, detail=f"API key required for {provider}")

    timeout = int(config.get("ai_timeout") or 10)
    timeout = min(timeout, 10)  # Cap test timeout at 10s
    model = config.get("ai_model") or ""

    try:
        if provider == "openai":
            from openai import OpenAI

            client = OpenAI(api_key=config["ai_api_key"], timeout=timeout)
            m = model or "gpt-4o-mini"
            response = client.chat.completions.create(
                model=m,
                messages=[{"role": "user", "content": "Say 'ok'"}],
                max_tokens=5,
            )
            return {
                "success": True,
                "message": f"Connected to OpenAI (model: {m})",
                "detail": response.choices[0].message.content,
            }

        elif provider == "anthropic":
            from anthropic import Anthropic

            client = Anthropic(api_key=config["ai_api_key"], timeout=timeout)
            m = model or "claude-sonnet-4-5-20250929"
            response = client.messages.create(
                model=m,
                max_tokens=5,
                messages=[{"role": "user", "content": "Say 'ok'"}],
            )
            return {
                "success": True,
                "message": f"Connected to Anthropic (model: {m})",
                "detail": response.content[0].text,
            }

        elif provider == "ollama":
            from openai import OpenAI

            base_url = config.get("ai_base_url") or ""
            base_url = base_url.rstrip("/") + "/v1" if base_url else "http://localhost:11434/v1"
            client = OpenAI(api_key="ollama", base_url=base_url, timeout=timeout)
            m = model or "llama3.2"
            response = client.chat.completions.create(
                model=m,
                messages=[{"role": "user", "content": "Say 'ok'"}],
                max_tokens=5,
            )
            return {
                "success": True,
                "message": f"Connected to Ollama (model: {m})",
                "detail": response.choices[0].message.content,
            }

    except Exception as exc:
        return {
            "success": False,
            "message": f"Connection failed: {exc}",
            "detail": str(exc),
        }


@router.delete("/ai")
def reset_ai_settings(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reset all DB-stored AI settings back to env var / defaults."""
    delete_all_ai_settings(db)
    logger.info("Admin '%s' reset AI settings to defaults", admin.username)
    return {"detail": "AI settings reset to defaults"}

"""Settings service — DB-first with in-memory cache and env var fallback."""

import logging
import time

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import decrypt_value, encrypt_value
from app.models.app_setting import AppSetting

logger = logging.getLogger(__name__)

# 5-minute cache
_CACHE_TTL = 300
_cache: dict[str, str | None] = {}
_cache_time: float = 0.0

# Keys that are encrypted in the DB
_SECRET_KEYS = {"ai_api_key"}

# Map setting keys to Settings attribute names for env var fallback
_ENV_FALLBACK = {
    "ai_provider": "AI_PROVIDER",
    "ai_api_key": "AI_API_KEY",
    "ai_model": "AI_MODEL",
    "ai_base_url": "AI_BASE_URL",
    "ai_max_text_length": "AI_MAX_TEXT_LENGTH",
    "ai_timeout": "AI_TIMEOUT",
    "ai_max_pages": "AI_MAX_PAGES",
    "ai_vision_dpi": "AI_VISION_DPI",
    "ai_vision_model": "AI_VISION_MODEL",
}

# All AI setting keys
AI_SETTING_KEYS = list(_ENV_FALLBACK.keys())


def clear_cache():
    """Clear the settings cache (call after writes)."""
    global _cache, _cache_time
    _cache = {}
    _cache_time = 0.0


def get_setting(db: Session, key: str) -> str | None:
    """Get a setting value: cache → DB → env var fallback."""
    global _cache, _cache_time

    # Check cache
    now = time.time()
    if now - _cache_time < _CACHE_TTL and key in _cache:
        return _cache[key]

    # Check DB
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is not None:
        value = row.value
        if row.is_secret and value:
            value = decrypt_value(value)
        _cache[key] = value
        _cache_time = now
        return value

    # Fall back to env var
    attr = _ENV_FALLBACK.get(key)
    if attr:
        return str(getattr(settings, attr, ""))

    return None


def get_setting_source(db: Session, key: str) -> str:
    """Return 'database', 'env', or 'default' for a given key."""
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is not None:
        return "database"

    attr = _ENV_FALLBACK.get(key)
    if attr:
        env_value = str(getattr(settings, attr, ""))
        default_value = str(settings.model_fields[attr].default)
        if env_value != default_value:
            return "env"

    return "default"


def get_all_ai_settings(db: Session) -> dict:
    """Return all AI settings as a dict with values and sources."""
    result = {}
    for key in AI_SETTING_KEYS:
        value = get_setting(db, key)
        source = get_setting_source(db, key)

        # Mask API key
        if key == "ai_api_key" and value:
            masked = "****" + value[-4:] if len(value) > 4 else "****"
            result[key] = {"value": masked, "source": source, "is_set": True}
        else:
            result[key] = {"value": value, "source": source}

    return result


def set_ai_settings(db: Session, data: dict):
    """Write AI settings to the DB, encrypting secrets. Clears cache."""
    for key, value in data.items():
        if key not in _ENV_FALLBACK:
            continue

        is_secret = key in _SECRET_KEYS
        store_value = value

        # Don't overwrite with the masked placeholder
        if is_secret and value and value.startswith("****"):
            continue

        if is_secret and store_value:
            store_value = encrypt_value(store_value)

        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        if row is None:
            row = AppSetting(key=key, value=store_value, is_secret=is_secret)
            db.add(row)
        else:
            row.value = store_value
            row.is_secret = is_secret

    db.commit()
    clear_cache()
    logger.info("AI settings updated in database")


def delete_all_ai_settings(db: Session):
    """Delete all DB-stored AI settings, reverting to env var / defaults."""
    db.query(AppSetting).filter(AppSetting.key.in_(AI_SETTING_KEYS)).delete(
        synchronize_session=False
    )
    db.commit()
    clear_cache()
    logger.info("AI settings reset to defaults")


def get_ai_config(db: Session) -> dict:
    """Return a flat dict of AI config values (for use by ai_provider)."""
    config = {}
    for key in AI_SETTING_KEYS:
        config[key] = get_setting(db, key)
    return config

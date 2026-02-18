"""Basic tests that don't require database or external services."""


def test_settings_importable():
    """Verify core config module loads without errors."""
    from app.core.config import settings

    assert settings.APP_NAME is not None
    assert settings.APP_VERSION is not None


def test_security_importable():
    """Verify security module loads."""
    from app.core.security import hash_password, verify_password

    hashed = hash_password("testpass123")
    assert verify_password("testpass123", hashed)
    assert not verify_password("wrong", hashed)

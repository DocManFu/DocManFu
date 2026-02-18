from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "DocManFu"
    APP_VERSION: str = "0.1.0"
    DATABASE_URL: str = "postgresql://docmanfu:docmanfu@localhost:5432/docmanfu"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    LOG_LEVEL: str = "INFO"
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 50

    # Celery / Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_TASK_MAX_RETRIES: int = 3
    CELERY_TASK_RETRY_DELAY: int = 60  # seconds

    # OCR
    OCR_LANGUAGE: str = "eng"  # Tesseract language code(s), e.g. "eng+fra"
    OCR_DPI: int = 300  # Resolution for rasterizing pages during OCR
    OCR_SKIP_TEXT: bool = True  # Skip pages that already contain text
    OCR_CLEAN: bool = True  # Clean intermediate files after OCR

    # AI Analysis
    AI_PROVIDER: str = "none"  # "openai", "anthropic", "ollama", or "none"
    AI_API_KEY: str = ""  # API key for the configured provider
    AI_MODEL: str = (
        ""  # Model name, e.g. "gpt-4o-mini", "claude-sonnet-4-5-20250929", "llama3.2"
    )
    AI_BASE_URL: str = (
        ""  # Custom base URL for OpenAI-compatible APIs (e.g. http://ollama:11434)
    )
    AI_MAX_TEXT_LENGTH: int = 4000  # Max chars of document text sent to AI
    AI_TIMEOUT: int = 60  # Seconds to wait for AI response
    AI_MAX_PAGES: int = 5  # Max PDF pages to send as images for vision analysis
    AI_VISION_DPI: int = 150  # Render resolution for vision analysis
    AI_VISION_MODEL: str = ""  # Vision model override (empty = use AI_MODEL)

    # JWT Authentication
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7


settings = Settings()

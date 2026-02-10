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


settings = Settings()

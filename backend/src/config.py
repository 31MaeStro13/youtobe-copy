"""
Конфигурация приложения на базе Pydantic Settings.
Загружает переменные окружения с валидацией типов и дефолтами.
"""

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Приложение
    APP_NAME: str = "YouTube Clone API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    EXTERNAL_PORT: int = 8080
    CORS_ORIGINS: List[str] = ["*"]

    # PostgreSQL
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "youtube_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/youtube_db",
        description="Async connection string for SQLAlchemy asyncpg",
    )
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True

    # MinIO S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_PUBLIC_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_VIDEOS: str = "videos"
    MINIO_BUCKET_THUMBNAILS: str = "thumbnails"
    MINIO_SECURE: bool = False
    PRESIGNED_URL_EXPIRATION_SECONDS: int = 3600  # 1 час для приватных видео

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Безопасность и JWT
    SECRET_KEY: str = "super-secret-jwt-key-replace-in-production-1234567890"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30


settings = Settings()

"""
Инициализация асинхронного движка SQLAlchemy 2.0 и фабрики сессий.
Включает пул соединений, health-check pre-ping и безопасное управление сессиями.
"""

from typing import AsyncGenerator
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.src.config import settings

# Именование ограничений (PK, FK, UQ, IX) по стандартам для однозначности в миграциях
POSTGRES_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_`%(constraint_name)s`",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Асинхронный движок с защитой от разрыва соединений (pre_ping)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
)

# Фабрика асинхронных сессий
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Базовый декларативный класс для всех моделей."""
    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency для внедрения сессии БД в эндпоинты.
    Гарантирует автоматический rollback при ошибках и закрытие соединения.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

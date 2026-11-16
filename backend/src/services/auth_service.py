"""
Auth Service — Argon2 хэширование паролей, JWT access/refresh токены, RBAC.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config import settings
from backend.src.models.user import User, UserRole


_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=2,
)


def hash_password(raw: str) -> str:
    return _ph.hash(raw)


def verify_password(hashed: str, raw: str) -> bool:
    try:
        _ph.verify(hashed, raw)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def _make_token(sub: str, role: str, token_type: str, expire_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expire_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: int, role: str) -> str:
    return _make_token(
        sub=str(user_id),
        role=role,
        token_type="access",
        expire_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int) -> str:
    return _make_token(
        sub=str(user_id),
        role="",
        token_type="refresh",
        expire_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    """Декодирует JWT и возвращает payload. Выбрасывает JWTError при невалидности."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


async def get_user_by_email_or_username(
    session: AsyncSession, login: str
) -> Optional[User]:
    """Ищет пользователя по email или username — один запрос вместо двух."""
    result = await session.execute(
        select(User).where(
            (User.email == login) | (User.username == login)
        )
    )
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def register_user(
    session: AsyncSession,
    email: str,
    username: str,
    password: str,
    role: UserRole = UserRole.USER,
) -> User:
    """Создает нового пользователя с Argon2 паролем."""
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        role=role,
    )
    session.add(user)
    await session.flush()  # получаем ID, но не коммитим (коммит в get_db)
    return user

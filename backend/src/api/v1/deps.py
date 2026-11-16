"""
FastAPI Dependencies — get_current_user, require_role.
Используется во всех защищённых эндпоинтах.
"""

from typing import List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.database import get_db
from backend.src.models.user import User, UserRole
from backend.src.services import auth_service

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Декодирует JWT, возвращает объект User. 401 при любой проблеме с токеном."""
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Невалидный или просроченный токен",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = auth_service.decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise exc
        user_id: int = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise exc

    user = await auth_service.get_user_by_id(session, user_id)
    if not user or not user.is_active:
        raise exc
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    session: AsyncSession = Depends(get_db),
) -> User | None:
    """Возвращает User или None, если токена нет (для публичных эндпоинтов)."""
    if not credentials:
        return None
    try:
        payload = auth_service.decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        user = await auth_service.get_user_by_id(session, int(payload["sub"]))
        return user if user and user.is_active else None
    except (JWTError, KeyError, ValueError):
        return None


def require_role(roles: List[UserRole]):
    """Фабрика зависимостей для проверки RBAC-роли."""
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Требуется роль: {[r.value for r in roles]}",
            )
        return user
    return _check

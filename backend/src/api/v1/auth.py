"""
Auth API — /api/v1/auth/register, /login, /refresh, /me
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.src.database import get_db
from backend.src.schemas.auth import UserRegister, UserLogin, TokenPair, RefreshTokenRequest
from backend.src.schemas.user import UserOut
from backend.src.services import auth_service
from backend.src.api.v1.deps import get_current_user
from backend.src.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: UserRegister, session: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.register_user(
            session, data.email, data.username, data.password
        )
    except IntegrityError:
        raise HTTPException(409, "Email или username уже занят")
    return user


@router.post("/login", response_model=TokenPair)
async def login(data: UserLogin, session: AsyncSession = Depends(get_db)):
    user = await auth_service.get_user_by_email_or_username(session, data.login)
    if not user or not auth_service.verify_password(user.hashed_password, data.password):
        raise HTTPException(401, "Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(403, "Аккаунт деактивирован")

    return TokenPair(
        access_token=auth_service.create_access_token(user.id, user.role.value),
        refresh_token=auth_service.create_refresh_token(user.id),
        user_id=user.id,
        username=user.username,
        role=user.role,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshTokenRequest, session: AsyncSession = Depends(get_db)):
    try:
        payload = auth_service.decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(401, "Невалидный refresh token")

    user = await auth_service.get_user_by_id(session, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Пользователь не найден")

    return TokenPair(
        access_token=auth_service.create_access_token(user.id, user.role.value),
        refresh_token=auth_service.create_refresh_token(user.id),
        user_id=user.id,
        username=user.username,
        role=user.role,
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user

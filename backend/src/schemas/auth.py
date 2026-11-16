"""
Pydantic-схемы аутентификации и авторизации (JWT / OAuth2).
"""

from pydantic import BaseModel, EmailStr, Field
from backend.src.models.user import UserRole


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    login: str = Field(description="Email или имя пользователя")
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: UserRole


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str # user_id
    role: str
    type: str = "access"

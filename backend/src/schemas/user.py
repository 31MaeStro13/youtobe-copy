"""
Pydantic-схемы для профилей пользователей.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr
from backend.src.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    username: str
    role: UserRole
    avatar_url: str | None = None


class UserOut(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    username: str | None = None
    avatar_url: str | None = None

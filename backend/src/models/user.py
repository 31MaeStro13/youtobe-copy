"""
Модель пользователя и перечисление ролей (RBAC).
"""

from enum import Enum
from typing import List, TYPE_CHECKING
from sqlalchemy import Boolean, Enum as SQLEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.database import Base
from backend.src.models.base import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from backend.src.models.channel import Channel, Subscription
    from backend.src.models.comment import Comment
    from backend.src.models.like import VideoLike, CommentLike
    from backend.src.models.report import Report
    from backend.src.models.video import VideoAccess


class UserRole(str, Enum):
    """Роли пользователей в системе (RBAC)."""
    USER = "user"           # Обычный пользователь (автор, зритель)
    MODERATOR = "moderator" # Модератор (просмотр жалоб, скрытие видео)
    ADMIN = "admin"         # Администратор (полные права)


class User(Base, IDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role_enum", values_callable=lambda x: [e.value for e in x]),
        default=UserRole.USER,
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Связи: explicit lazy='raise' предотвращает случайные N+1 запросы в асинхронном коде
    channels: Mapped[List["Channel"]] = relationship(
        "Channel",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription",
        back_populates="subscriber",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    comments: Mapped[List["Comment"]] = relationship(
        "Comment",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    video_likes: Mapped[List["VideoLike"]] = relationship(
        "VideoLike",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    comment_likes: Mapped[List["CommentLike"]] = relationship(
        "CommentLike",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    reports_submitted: Mapped[List["Report"]] = relationship(
        "Report",
        foreign_keys="[Report.reporter_id]",
        back_populates="reporter",
        lazy="raise",
    )
    private_video_access: Mapped[List["VideoAccess"]] = relationship(
        "VideoAccess",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )

"""
Модели видеороликов и разграничения доступа к приватным видео.
Включает композитные индексы для оптимизации выборки публичной ленты без N+1.
"""

from enum import Enum
from typing import List, TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.database import Base
from backend.src.models.base import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from backend.src.models.channel import Channel
    from backend.src.models.comment import Comment
    from backend.src.models.like import VideoLike
    from backend.src.models.report import Report
    from backend.src.models.user import User


class VideoStatus(str, Enum):
    """Статусы готовности видео."""
    PROCESSING = "processing" # Видео залито, обрабатывается в Celery/FFmpeg
    READY = "ready"           # Обработка завершена, готово к стримингу
    FAILED = "failed"         # Ошибка конвертации или битый файл


class VideoPrivacy(str, Enum):
    """Уровни приватности видео."""
    PUBLIC = "public"     # Доступно всем в поиске и ленте
    UNLISTED = "unlisted" # Доступно только по прямой ссылке
    PRIVATE = "private"   # Доступно только автору и пользователям из VideoAccess


class Video(Base, IDMixin, TimestampMixin):
    __tablename__ = "videos"
    __table_args__ = (
        # Композитный индекс для ультрабыстрой фильтрации главной ленты
        Index(
            "ix_videos_feed_lookup",
            "is_hidden_by_mod",
            "privacy",
            "status",
            "created_at",
        ),
        # Индекс для поиска по названию
        Index("ix_videos_title_search", "title"),
    )

    channel_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Хранилище MinIO S3
    video_s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Метаданные медиа
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    views_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    likes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dislikes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Статусы и модерация
    status: Mapped[VideoStatus] = mapped_column(
        SQLEnum(VideoStatus, name="video_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=VideoStatus.PROCESSING,
        nullable=False,
        index=True,
    )
    privacy: Mapped[VideoPrivacy] = mapped_column(
        SQLEnum(VideoPrivacy, name="video_privacy_enum", values_callable=lambda x: [e.value for e in x]),
        default=VideoPrivacy.PUBLIC,
        nullable=False,
        index=True,
    )
    is_hidden_by_mod: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    # Связи
    channel: Mapped["Channel"] = relationship(
        "Channel",
        back_populates="videos",
        lazy="raise",
    )
    comments: Mapped[List["Comment"]] = relationship(
        "Comment",
        back_populates="video",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    likes: Mapped[List["VideoLike"]] = relationship(
        "VideoLike",
        back_populates="video",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    reports: Mapped[List["Report"]] = relationship(
        "Report",
        back_populates="video",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    allowed_users: Mapped[List["VideoAccess"]] = relationship(
        "VideoAccess",
        back_populates="video",
        cascade="all, delete-orphan",
        lazy="raise",
    )


class VideoAccess(Base, IDMixin, TimestampMixin):
    """Белый список пользователей, имеющих доступ к приватному видео."""
    __tablename__ = "video_access"
    __table_args__ = (
        UniqueConstraint("video_id", "user_id", name="uq_video_user_access"),
    )

    video_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    video: Mapped["Video"] = relationship("Video", back_populates="allowed_users", lazy="raise")
    user: Mapped["User"] = relationship("User", back_populates="private_video_access", lazy="raise")

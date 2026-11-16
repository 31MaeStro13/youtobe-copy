"""
Модель жалоб на видео (Report) для панели модерации.
Включает статусы рассмотрения, причины жалоб и аудит действий модератора.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.database import Base
from backend.src.models.base import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from backend.src.models.user import User
    from backend.src.models.video import Video


class ReportReason(str, Enum):
    """Причины жалобы на видео."""
    SPAM = "spam"
    INAPPROPRIATE = "inappropriate"
    COPYRIGHT = "copyright"
    VIOLENCE = "violence"
    OTHER = "other"


class ReportStatus(str, Enum):
    """Статусы рассмотрения жалобы модератором."""
    PENDING = "pending"       # Ожидает рассмотрения
    RESOLVED = "resolved"     # Нарушение подтверждено (видео скрыто/удалено)
    DISMISSED = "dismissed"   # Жалоба отклонена модератором


class Report(Base, IDMixin, TimestampMixin):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_status_created_at", "status", "created_at"),
    )

    video_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reporter_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason: Mapped[ReportReason] = mapped_column(
        SQLEnum(ReportReason, name="report_reason_enum", values_callable=lambda x: [e.value for e in x]),
        default=ReportReason.OTHER,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Статус рассмотрения
    status: Mapped[ReportStatus] = mapped_column(
        SQLEnum(ReportStatus, name="report_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=ReportStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Аудит модерации
    moderator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    moderator_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Связи (lazy='raise' для исключения N+1)
    video: Mapped["Video"] = relationship("Video", back_populates="reports", lazy="raise")
    reporter: Mapped["User"] = relationship(
        "User",
        foreign_keys=[reporter_id],
        back_populates="reports_submitted",
        lazy="raise",
    )
    moderator: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[moderator_id],
        lazy="raise",
    )

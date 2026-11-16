"""
Pydantic-схемы для модерации и жалоб на видео.
"""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend.src.models.report import ReportReason, ReportStatus


class ReportCreate(BaseModel):
    video_id: int
    reason: ReportReason = ReportReason.OTHER
    description: str | None = Field(default=None, max_length=1000)


class ReportOut(BaseModel):
    id: int
    video_id: int
    reporter_id: int
    reason: ReportReason
    description: str | None = None
    status: ReportStatus
    moderator_id: int | None = None
    moderator_notes: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime

    # Контекстные данные для удобства модератора
    video_title: str | None = None
    reporter_username: str | None = None
    moderator_username: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ReportResolveRequest(BaseModel):
    action: Literal["hide", "dismiss", "delete"] = Field(
        description="'hide' - скрыть видео от публики, 'dismiss' - отклонить жалобу, 'delete' - удалить видео навсегда"
    )
    moderator_notes: str | None = None

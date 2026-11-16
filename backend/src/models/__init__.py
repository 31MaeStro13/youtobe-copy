"""
Экспорт всех моделей и перечислений для легкого импорта и регистрации в Alembic.
"""

from backend.src.database import Base
from backend.src.models.base import IDMixin, TimestampMixin
from backend.src.models.user import User, UserRole
from backend.src.models.channel import Channel, Subscription
from backend.src.models.video import Video, VideoStatus, VideoPrivacy, VideoAccess
from backend.src.models.comment import Comment
from backend.src.models.like import VideoLike, CommentLike
from backend.src.models.report import Report, ReportReason, ReportStatus

__all__ = [
    "Base",
    "IDMixin",
    "TimestampMixin",
    "User",
    "UserRole",
    "Channel",
    "Subscription",
    "Video",
    "VideoStatus",
    "VideoPrivacy",
    "VideoAccess",
    "Comment",
    "VideoLike",
    "CommentLike",
    "Report",
    "ReportReason",
    "ReportStatus",
]

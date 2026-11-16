"""
Модели лайков и дизлайков для видеороликов и комментариев.
"""

from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.database import Base
from backend.src.models.base import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from backend.src.models.comment import Comment
    from backend.src.models.user import User
    from backend.src.models.video import Video


class VideoLike(Base, IDMixin, TimestampMixin):
    """Лайк или дизлайк к видео. Один пользователь может поставить только одну оценку."""
    __tablename__ = "video_likes"
    __table_args__ = (
        UniqueConstraint("user_id", "video_id", name="uq_user_video_like"),
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_like: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="True - лайк, False - дизлайк",
    )

    user: Mapped["User"] = relationship("User", back_populates="video_likes", lazy="raise")
    video: Mapped["Video"] = relationship("Video", back_populates="likes", lazy="raise")


class CommentLike(Base, IDMixin, TimestampMixin):
    """Лайк к комментарию."""
    __tablename__ = "comment_likes"
    __table_args__ = (
        UniqueConstraint("user_id", "comment_id", name="uq_user_comment_like"),
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    comment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="comment_likes", lazy="raise")
    comment: Mapped["Comment"] = relationship("Comment", back_populates="likes", lazy="raise")

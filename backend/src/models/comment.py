"""
Модель комментариев с поддержкой древовидных ответов (parent_id).
"""

from typing import List, TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.database import Base
from backend.src.models.base import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from backend.src.models.like import CommentLike
    from backend.src.models.user import User
    from backend.src.models.video import Video


class Comment(Base, IDMixin, TimestampMixin):
    __tablename__ = "comments"

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
    parent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    text: Mapped[str] = mapped_column(Text, nullable=False)
    likes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Связи
    video: Mapped["Video"] = relationship("Video", back_populates="comments", lazy="raise")
    user: Mapped["User"] = relationship("User", back_populates="comments", lazy="raise")
    parent: Mapped["Comment | None"] = relationship(
        "Comment",
        remote_side="Comment.id",
        back_populates="replies",
        lazy="raise",
    )
    replies: Mapped[List["Comment"]] = relationship(
        "Comment",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    likes: Mapped[List["CommentLike"]] = relationship(
        "CommentLike",
        back_populates="comment",
        cascade="all, delete-orphan",
        lazy="raise",
    )

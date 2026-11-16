"""
Модели канала автора и подписок на каналы.
"""

from typing import List, TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.database import Base
from backend.src.models.base import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from backend.src.models.user import User
    from backend.src.models.video import Video


class Channel(Base, IDMixin, TimestampMixin):
    __tablename__ = "channels"

    owner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subscribers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Связи
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="channels",
        lazy="raise",
    )
    videos: Mapped[List["Video"]] = relationship(
        "Video",
        back_populates="channel",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    subscribers: Mapped[List["Subscription"]] = relationship(
        "Subscription",
        back_populates="channel",
        cascade="all, delete-orphan",
        lazy="raise",
    )


class Subscription(Base, IDMixin, TimestampMixin):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("subscriber_id", "channel_id", name="uq_subscriber_channel"),
    )

    subscriber_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    subscriber: Mapped["User"] = relationship(
        "User",
        back_populates="subscriptions",
        lazy="raise",
    )
    channel: Mapped["Channel"] = relationship(
        "Channel",
        back_populates="subscribers",
        lazy="raise",
    )

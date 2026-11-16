"""
Pydantic-схемы для каналов авторов и подписок.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ChannelCreate(BaseModel):
    title: str = Field(min_length=2, max_length=128)
    description: str | None = None
    avatar_url: str | None = None
    banner_url: str | None = None


class ChannelUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=128)
    description: str | None = None
    avatar_url: str | None = None
    banner_url: str | None = None


class ChannelOut(BaseModel):
    id: int
    owner_id: int
    title: str
    description: str | None = None
    avatar_url: str | None = None
    banner_url: str | None = None
    subscribers_count: int
    created_at: datetime
    is_subscribed: bool = False

    model_config = ConfigDict(from_attributes=True)


class SubscriptionOut(BaseModel):
    channel_id: int
    subscriber_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

"""
Pydantic-схемы для видеороликов, ленты, оценок и доступа к приватным видео.
"""

from datetime import datetime
from typing import List
from pydantic import BaseModel, ConfigDict, Field
from backend.src.models.video import VideoPrivacy, VideoStatus


class VideoCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    privacy: VideoPrivacy = VideoPrivacy.PUBLIC
    allowed_user_ids: List[int] = Field(default_factory=list, description="ID пользователей для доступа к приватному видео")


class VideoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    privacy: VideoPrivacy | None = None
    allowed_user_ids: List[int] | None = None


class VideoFeedItem(BaseModel):
    """Легковесная карточка видеоролика для быстрой отдачи главной ленты и результатов поиска."""
    id: int
    title: str
    thumbnail_url: str | None = None
    duration_seconds: int = 0
    views_count: int = 0
    created_at: datetime
    channel_id: int
    channel_title: str
    channel_avatar: str | None = None

    model_config = ConfigDict(from_attributes=True)


class VideoDetailOut(BaseModel):
    """Полная детальная информация о видеоролике для страницы плеера."""
    id: int
    channel_id: int
    title: str
    description: str | None = None
    video_s3_key: str
    thumbnail_s3_key: str | None = None
    duration_seconds: int = 0
    views_count: int = 0
    likes_count: int = 0
    dislikes_count: int = 0
    status: VideoStatus
    privacy: VideoPrivacy
    is_hidden_by_mod: bool
    created_at: datetime
    
    # Расширенная информация
    channel_title: str
    channel_avatar: str | None = None
    channel_subscribers_count: int = 0
    stream_url: str | None = None
    thumbnail_url: str | None = None
    user_reaction: bool | None = None  # True - like, False - dislike, None - нет оценки
    is_subscribed: bool = False
    is_owner: bool = False

    model_config = ConfigDict(from_attributes=True)


class VideoLikeRequest(BaseModel):
    is_like: bool = Field(description="True для лайка, False для дизлайка")


class VideoAccessAddRequest(BaseModel):
    user_ids: List[int]

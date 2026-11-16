"""
Pydantic-схемы для комментариев к видео и древовидных ответов.
"""

from datetime import datetime
from typing import List
from pydantic import BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    parent_id: int | None = None


class CommentOut(BaseModel):
    id: int
    video_id: int
    user_id: int
    parent_id: int | None = None
    text: str
    likes_count: int = 0
    is_hidden: bool = False
    created_at: datetime

    author_username: str
    author_avatar: str | None = None
    replies_count: int = 0
    user_liked: bool = False

    model_config = ConfigDict(from_attributes=True)

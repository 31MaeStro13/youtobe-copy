"""
Экспорт Pydantic-схем проекта YouTube Clone.
"""

from backend.src.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenPair,
    RefreshTokenRequest,
    TokenPayload,
)
from backend.src.schemas.user import (
    UserBase,
    UserOut,
    UserUpdate,
)
from backend.src.schemas.channel import (
    ChannelCreate,
    ChannelUpdate,
    ChannelOut,
    SubscriptionOut,
)
from backend.src.schemas.video import (
    VideoCreate,
    VideoUpdate,
    VideoFeedItem,
    VideoDetailOut,
    VideoLikeRequest,
    VideoAccessAddRequest,
)
from backend.src.schemas.comment import (
    CommentCreate,
    CommentOut,
)
from backend.src.schemas.report import (
    ReportCreate,
    ReportOut,
    ReportResolveRequest,
)

__all__ = [
    "UserRegister",
    "UserLogin",
    "TokenPair",
    "RefreshTokenRequest",
    "TokenPayload",
    "UserBase",
    "UserOut",
    "UserUpdate",
    "ChannelCreate",
    "ChannelUpdate",
    "ChannelOut",
    "SubscriptionOut",
    "VideoCreate",
    "VideoUpdate",
    "VideoFeedItem",
    "VideoDetailOut",
    "VideoLikeRequest",
    "VideoAccessAddRequest",
    "CommentCreate",
    "CommentOut",
    "ReportCreate",
    "ReportOut",
    "ReportResolveRequest",
]

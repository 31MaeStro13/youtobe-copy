"""
Channels API — CRUD каналов, подписки.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.src.database import get_db
from backend.src.models.channel import Channel, Subscription
from backend.src.models.user import User
from backend.src.schemas.channel import ChannelCreate, ChannelUpdate, ChannelOut
from backend.src.schemas.video import VideoFeedItem
from backend.src.services import video_service
from backend.src.api.v1.deps import get_current_user, get_current_user_optional
from backend.src.config import settings

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("/my", response_model=list[ChannelOut])
async def my_channels(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(Channel).where(Channel.owner_id == user.id).order_by(Channel.created_at.asc())
    )
    channels = result.scalars().all()
    return [_map_channel(c) for c in channels]


@router.post("/", response_model=ChannelOut, status_code=201)
async def create_channel(
    data: ChannelCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    channel = Channel(owner_id=user.id, **data.model_dump())
    session.add(channel)
    await session.flush()
    return _map_channel(channel)


@router.get("/{channel_id}", response_model=ChannelOut)
async def get_channel(
    channel_id: int,
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    result = await session.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404)

    is_subscribed = False
    if user:
        sub = await session.execute(
            select(Subscription).where(
                Subscription.subscriber_id == user.id,
                Subscription.channel_id == channel_id,
            )
        )
        is_subscribed = sub.scalar_one_or_none() is not None

    return _map_channel(channel, is_subscribed)


@router.patch("/{channel_id}", response_model=ChannelOut)
async def update_channel(
    channel_id: int,
    data: ChannelUpdate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await session.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel or channel.owner_id != user.id:
        raise HTTPException(403)

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(channel, field, value)
    await session.flush()
    return _map_channel(channel)


@router.get("/{channel_id}/videos", response_model=list[VideoFeedItem])
async def channel_videos(
    channel_id: int,
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    videos = await video_service.get_channel_videos(session, channel_id, user)
    items = []
    for v in videos:
        thumb_url = f"/api/v1/videos/{v.id}/thumbnail" if v.thumbnail_s3_key else None
        items.append(VideoFeedItem(
            id=v.id,
            title=v.title,
            thumbnail_url=thumb_url,
            duration_seconds=v.duration_seconds,
            views_count=v.views_count,
            created_at=v.created_at,
            channel_id=v.channel_id,
            channel_title=v.channel.title,
            channel_avatar=v.channel.avatar_url,
        ))
    return items


@router.post("/{channel_id}/subscribe", status_code=201)
async def subscribe(
    channel_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await session.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Канал не найден")
    if channel.owner_id == user.id:
        raise HTTPException(400, "Нельзя подписаться на свой собственный канал")

    try:
        session.add(Subscription(subscriber_id=user.id, channel_id=channel_id))
        await session.flush()
        # Атомарный инкремент подписчиков
        await session.execute(
            update(Channel).where(Channel.id == channel_id)
            .values(subscribers_count=Channel.subscribers_count + 1)
        )
    except IntegrityError:
        raise HTTPException(409, "Уже подписан")
    return {"subscribed": True}


@router.delete("/{channel_id}/subscribe", status_code=204)
async def unsubscribe(
    channel_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(Subscription).where(
            Subscription.subscriber_id == user.id,
            Subscription.channel_id == channel_id,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Подписка не найдена")

    await session.delete(sub)
    await session.execute(
        update(Channel).where(Channel.id == channel_id)
        .values(subscribers_count=func.greatest(Channel.subscribers_count - 1, 0))
    )


def _map_channel(channel: Channel, is_subscribed: bool = False) -> ChannelOut:
    return ChannelOut(
        id=channel.id,
        owner_id=channel.owner_id,
        title=channel.title,
        description=channel.description,
        avatar_url=channel.avatar_url,
        banner_url=channel.banner_url,
        subscribers_count=channel.subscribers_count,
        created_at=channel.created_at,
        is_subscribed=is_subscribed,
    )

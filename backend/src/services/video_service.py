"""
Video Service — CRUD видеороликов, проверки RBAC/доступа, лайки, просмотры.
Все запросы используют явный selectinload/joinedload — no N+1.
"""

from typing import List, Optional
from sqlalchemy import select, update, func, delete
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.src.models.video import Video, VideoStatus, VideoPrivacy, VideoAccess
from backend.src.models.channel import Channel
from backend.src.models.like import VideoLike
from backend.src.models.user import User, UserRole
from backend.src.schemas.video import VideoCreate, VideoUpdate


FEED_PAGE_SIZE = 20


async def get_feed(
    session: AsyncSession,
    page: int = 1,
    search: Optional[str] = None,
) -> List[Video]:
    """
    Главная лента: только публичные, готовые, не скрытые видео.
    Использует композитный индекс ix_videos_feed_lookup.
    """
    page = max(1, page)
    stmt = (
        select(Video)
        .where(
            Video.is_hidden_by_mod == False,
            Video.privacy == VideoPrivacy.PUBLIC,
            Video.status == VideoStatus.READY,
        )
        .options(joinedload(Video.channel))  # 1 JOIN вместо N SELECT
        .order_by(Video.created_at.desc())
        .offset((page - 1) * FEED_PAGE_SIZE)
        .limit(FEED_PAGE_SIZE)
    )
    if search:
        stmt = stmt.where(Video.title.ilike(f"%{search}%"))

    result = await session.execute(stmt)
    return result.scalars().all()


async def get_video_by_id(
    session: AsyncSession,
    video_id: int,
    requesting_user: Optional[User] = None,
) -> Optional[Video]:
    """
    Получает видео с проверкой прав доступа:
    - PUBLIC/UNLISTED → доступны всем
    - PRIVATE → только автор канала или пользователь из VideoAccess
    - HIDDEN_BY_MOD → только модератор/admin
    """
    stmt = (
        select(Video)
        .where(Video.id == video_id)
        .options(joinedload(Video.channel))
    )
    result = await session.execute(stmt)
    video = result.scalar_one_or_none()
    if not video:
        return None

    if video.is_hidden_by_mod:
        if not requesting_user or requesting_user.role not in (UserRole.MODERATOR, UserRole.ADMIN):
            return None

    if video.privacy == VideoPrivacy.PRIVATE:
        if not requesting_user:
            return None
        is_owner = video.channel.owner_id == requesting_user.id
        if not is_owner:
            # Проверяем whitelist
            access = await session.execute(
                select(VideoAccess).where(
                    VideoAccess.video_id == video_id,
                    VideoAccess.user_id == requesting_user.id,
                )
            )
            if not access.scalar_one_or_none():
                return None

    return video


async def create_video_record(
    session: AsyncSession,
    channel_id: int,
    s3_key: str,
    data: VideoCreate,
) -> Video:
    """Создаёт запись видео в БД (статус PROCESSING до завершения Celery-задачи)."""
    video = Video(
        channel_id=channel_id,
        title=data.title,
        description=data.description,
        video_s3_key=s3_key,
        privacy=data.privacy,
        status=VideoStatus.PROCESSING,
    )
    session.add(video)
    await session.flush()

    # Добавляем whitelist для приватных видео
    if data.privacy == VideoPrivacy.PRIVATE and data.allowed_user_ids:
        for uid in data.allowed_user_ids:
            session.add(VideoAccess(video_id=video.id, user_id=uid))

    return video


async def update_video(
    session: AsyncSession,
    video: Video,
    data: VideoUpdate,
    requesting_user: User,
) -> Video:
    """Обновляет метаданные видео — только автор канала или admin."""
    channel_result = await session.execute(
        select(Channel).where(Channel.id == video.channel_id)
    )
    channel = channel_result.scalar_one()
    if channel.owner_id != requesting_user.id and requesting_user.role != UserRole.ADMIN:
        raise PermissionError("Нет прав на редактирование")

    if data.title is not None:
        video.title = data.title
    if data.description is not None:
        video.description = data.description
    if data.privacy is not None:
        video.privacy = data.privacy

    if data.allowed_user_ids is not None:
        await session.execute(
            delete(VideoAccess).where(VideoAccess.video_id == video.id)
        )
        for uid in data.allowed_user_ids:
            session.add(VideoAccess(video_id=video.id, user_id=uid))

    await session.flush()
    return video


async def increment_views(session: AsyncSession, video_id: int) -> None:
    """Атомарный инкремент просмотров без race condition."""
    await session.execute(
        update(Video)
        .where(Video.id == video_id)
        .values(views_count=Video.views_count + 1)
    )


async def set_like(
    session: AsyncSession,
    video_id: int,
    user_id: int,
    is_like: bool,
) -> None:
    """
    Upsert лайка/дизлайка. При конфликте обновляет флаг is_like.
    Атомарно корректирует счетчики likes_count / dislikes_count.
    """
    existing = await session.execute(
        select(VideoLike).where(
            VideoLike.video_id == video_id,
            VideoLike.user_id == user_id,
        )
    )
    existing_like = existing.scalar_one_or_none()

    from sqlalchemy import func

    if existing_like:
        if existing_like.is_like == is_like:
            # Повторное нажатие — снять оценку (защита от отрицательных чисел)
            await session.delete(existing_like)
            if is_like:
                await session.execute(
                    update(Video).where(Video.id == video_id).values(
                        likes_count=func.greatest(Video.likes_count - 1, 0)
                    )
                )
            else:
                await session.execute(
                    update(Video).where(Video.id == video_id).values(
                        dislikes_count=func.greatest(Video.dislikes_count - 1, 0)
                    )
                )
        else:
            # Переключить с лайка на дизлайк или наоборот
            existing_like.is_like = is_like
            if is_like:
                await session.execute(
                    update(Video).where(Video.id == video_id).values(
                        likes_count=Video.likes_count + 1,
                        dislikes_count=func.greatest(Video.dislikes_count - 1, 0),
                    )
                )
            else:
                await session.execute(
                    update(Video).where(Video.id == video_id).values(
                        likes_count=func.greatest(Video.likes_count - 1, 0),
                        dislikes_count=Video.dislikes_count + 1,
                    )
                )
    else:
        session.add(VideoLike(video_id=video_id, user_id=user_id, is_like=is_like))
        col = Video.likes_count if is_like else Video.dislikes_count
        await session.execute(
            update(Video).where(Video.id == video_id).values({col: col + 1})
        )


async def get_channel_videos(
    session: AsyncSession,
    channel_id: int,
    requesting_user: Optional[User] = None,
) -> List[Video]:
    """Видео конкретного канала с учётом прав на приватные."""
    # Проверяем владельца канала
    channel_res = await session.execute(select(Channel).where(Channel.id == channel_id))
    channel = channel_res.scalar_one_or_none()
    is_owner = requesting_user and channel and channel.owner_id == requesting_user.id
    is_staff = requesting_user and requesting_user.role in (UserRole.MODERATOR, UserRole.ADMIN)

    conditions = [Video.channel_id == channel_id]

    if not is_owner and not is_staff:
        conditions.append(Video.status == VideoStatus.READY)
        conditions.append(Video.privacy == VideoPrivacy.PUBLIC)
        conditions.append(Video.is_hidden_by_mod == False)
    elif not is_staff:
        conditions.append(Video.is_hidden_by_mod == False)

    result = await session.execute(
        select(Video)
        .where(*conditions)
        .options(joinedload(Video.channel))
        .order_by(Video.created_at.desc())
    )
    return result.scalars().all()

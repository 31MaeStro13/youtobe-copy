"""
Videos API — CRUD видео, Upload, HTTP 206 Range Streaming, лайки, доступ.
"""

import uuid
from typing import Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException,
    Request, Response, UploadFile, status
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.database import get_db
from backend.src.models.user import User, UserRole
from backend.src.models.video import VideoPrivacy, VideoStatus
from backend.src.schemas.video import (
    VideoCreate, VideoUpdate, VideoDetailOut, VideoFeedItem, VideoLikeRequest
)
from backend.src.services import video_service, storage_service
from backend.src.services.auth_service import get_user_by_id
from backend.src.api.v1.deps import get_current_user, get_current_user_optional, require_role
from backend.src.worker.tasks import process_video
from backend.src.config import settings

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("/", response_model=list[VideoFeedItem])
async def feed(
    page: int = 1,
    search: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    videos = await video_service.get_feed(session, page=page, search=search)
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


@router.post("/upload", status_code=201)
async def upload_video(
    title: str = Form(...),
    description: str = Form(None),
    privacy: VideoPrivacy = Form(VideoPrivacy.PUBLIC),
    channel_id: int = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Принимает видеофайл, кладёт в S3, создаёт запись, запускает Celery worker."""
    from sqlalchemy import select
    from backend.src.models.channel import Channel

    # Проверяем что канал принадлежит пользователю
    result = await session.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel or channel.owner_id != user.id:
        raise HTTPException(403, "Нет прав на загрузку в этот канал")

    # Проверяем тип файла
    allowed = {"video/mp4", "video/webm", "video/avi", "video/quicktime", "video/x-matroska"}
    if file.content_type not in allowed:
        raise HTTPException(415, f"Неподдерживаемый формат: {file.content_type}")

    # Лимит 2GB
    content = await file.read()
    if len(content) > 2 * 1024 * 1024 * 1024:
        raise HTTPException(413, "Файл превышает лимит 2GB")

    s3_key = f"videos/{uuid.uuid4().hex}_{file.filename}"
    await storage_service.upload_file(
        settings.MINIO_BUCKET_VIDEOS, s3_key, content, file.content_type or "video/mp4"
    )

    video = await video_service.create_video_record(
        session, channel_id, s3_key,
        VideoCreate(title=title, description=description, privacy=privacy)
    )
    await session.commit()

    # Запускаем Celery задачу обработки FFmpeg
    process_video.delay(video.id, s3_key)

    return {"id": video.id, "status": video.status.value, "s3_key": s3_key}


@router.get("/{video_id}", response_model=VideoDetailOut)
async def get_video(
    video_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    video = await video_service.get_video_by_id(session, video_id, user)
    if not video:
        raise HTTPException(404, "Видео не найдено или доступ запрещён")

    # Дедупликация просмотров: не чаще 1 раза в 60 секунд на IP/пользователя
    from fastapi import Request
    client_ip = request.client.host if request.client else "unknown"
    viewer_key = f"viewed:{video_id}:{user.id if user else client_ip}"

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL)
        is_new = await r.set(viewer_key, "1", ex=60, nx=True)
        await r.aclose()
        if is_new:
            await video_service.increment_views(session, video_id)
    except Exception:
        # Fallback если redis недоступен
        await video_service.increment_views(session, video_id)

    # Генерируем URL для стриминга
    if video.privacy == VideoPrivacy.PRIVATE:
        stream_url = await storage_service.generate_presigned_url(
            settings.MINIO_BUCKET_VIDEOS, video.video_s3_key
        )
        thumb_url = None
        if video.thumbnail_s3_key:
            thumb_url = await storage_service.generate_presigned_url(
                settings.MINIO_BUCKET_THUMBNAILS, video.thumbnail_s3_key
            )
    else:
        stream_url = f"/api/v1/videos/{video_id}/stream"
        thumb_url = f"/api/v1/videos/{video_id}/thumbnail" if video.thumbnail_s3_key else None

    # Реакция текущего пользователя
    user_reaction = None
    if user:
        from sqlalchemy import select
        from backend.src.models.like import VideoLike
        like_res = await session.execute(
            select(VideoLike).where(VideoLike.video_id == video_id, VideoLike.user_id == user.id)
        )
        like = like_res.scalar_one_or_none()
        user_reaction = like.is_like if like else None

    return VideoDetailOut(
        id=video.id,
        channel_id=video.channel_id,
        title=video.title,
        description=video.description,
        video_s3_key=video.video_s3_key,
        thumbnail_s3_key=video.thumbnail_s3_key,
        duration_seconds=video.duration_seconds,
        views_count=video.views_count,
        likes_count=video.likes_count,
        dislikes_count=video.dislikes_count,
        status=video.status,
        privacy=video.privacy,
        is_hidden_by_mod=video.is_hidden_by_mod,
        created_at=video.created_at,
        channel_title=video.channel.title,
        channel_avatar=video.channel.avatar_url,
        channel_subscribers_count=video.channel.subscribers_count,
        stream_url=stream_url,
        thumbnail_url=thumb_url,
        user_reaction=user_reaction,
        is_owner=user.id == video.channel.owner_id if user else False,
    )


@router.api_route("/{video_id}/stream", methods=["GET", "HEAD"])
async def stream_video(
    video_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    HTTP 206 Range Streaming — поддержка перемотки в HTML5 <video>.
    Приватные видео → redirect на presigned URL.
    """
    video = await video_service.get_video_by_id(session, video_id, user)
    if not video:
        raise HTTPException(404, "Видео не найдено")

    if video.status != VideoStatus.READY:
        raise HTTPException(409, f"Видео в обработке или недоступно (статус: {video.status.value})")

    if video.privacy == VideoPrivacy.PRIVATE:
        url = await storage_service.generate_presigned_url(
            settings.MINIO_BUCKET_VIDEOS, video.video_s3_key
        )
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url)

    range_header = request.headers.get("Range")

    data = b""
    start_byte = end_byte = total = 0
    async for chunk, start, end, size in storage_service.stream_range(
        settings.MINIO_BUCKET_VIDEOS, video.video_s3_key, range_header
    ):
        data = chunk
        start_byte, end_byte, total = start, end, size
        break

    headers = {
        "Content-Range": f"bytes {start_byte}-{end_byte}/{total}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(len(data)),
        "Content-Type": "video/mp4",
    }
    return Response(
        content=data,
        status_code=206 if range_header else 200,
        headers=headers,
        media_type="video/mp4",
    )


@router.api_route("/{video_id}/thumbnail", methods=["GET", "HEAD"])
async def video_thumbnail(
    video_id: int,
    session: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Отдаёт WebP превью видео с кэшированием и строгой проверкой прав доступа."""
    video = await video_service.get_video_by_id(session, video_id, user)
    if not video or not video.thumbnail_s3_key:
        raise HTTPException(404, "Thumbnail not found")

    import aioboto3
    s3_session = aioboto3.Session()
    s3_kwargs = dict(
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name="us-east-1",
    )
    async with s3_session.client("s3", **s3_kwargs) as s3:
        try:
            resp = await s3.get_object(
                Bucket=settings.MINIO_BUCKET_THUMBNAILS,
                Key=video.thumbnail_s3_key,
            )
            async with resp["Body"] as stream:
                content = await stream.read()
            return Response(
                content=content,
                media_type="image/webp",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        except Exception:
            raise HTTPException(404, "Thumbnail not found")


@router.post("/{video_id}/like")
async def like_video(
    video_id: int,
    data: VideoLikeRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = await video_service.get_video_by_id(session, video_id, user)
    if not video:
        raise HTTPException(404, "Видео не найдено")

    from sqlalchemy.exc import IntegrityError
    try:
        await video_service.set_like(session, video_id, user.id, data.is_like)
    except IntegrityError:
        await session.rollback()
    return {"ok": True}


@router.patch("/{video_id}")
async def update_video(
    video_id: int,
    data: VideoUpdate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = await video_service.get_video_by_id(session, video_id, user)
    if not video:
        raise HTTPException(404)
    try:
        updated = await video_service.update_video(session, video, data, user)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    return {"id": updated.id, "title": updated.title, "privacy": updated.privacy.value}


@router.delete("/{video_id}", status_code=204)
async def delete_video(
    video_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from sqlalchemy import select, delete as sql_delete
    from backend.src.models.channel import Channel

    video = await video_service.get_video_by_id(session, video_id, user)
    if not video:
        raise HTTPException(404)

    channel_res = await session.execute(select(Channel).where(Channel.id == video.channel_id))
    channel = channel_res.scalar_one()
    is_owner = channel.owner_id == user.id
    is_admin = user.role == UserRole.ADMIN

    if not is_owner and not is_admin:
        raise HTTPException(403)

    v_key = video.video_s3_key
    t_key = video.thumbnail_s3_key

    # Сначала удаляем запись в БД
    await session.delete(video)
    await session.flush()

    # Затем безопасно очищаем объекты в S3
    await storage_service.delete_object(settings.MINIO_BUCKET_VIDEOS, v_key)
    if t_key:
        await storage_service.delete_object(settings.MINIO_BUCKET_THUMBNAILS, t_key)

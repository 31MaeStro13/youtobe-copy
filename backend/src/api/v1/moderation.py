"""
Moderation API — панель модератора: жалобы, скрытие/удаление видео.
Доступ: только MODERATOR и ADMIN.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.database import get_db
from backend.src.models.report import Report, ReportStatus
from backend.src.models.video import Video
from backend.src.models.user import User, UserRole
from backend.src.schemas.report import ReportCreate, ReportOut, ReportResolveRequest
from backend.src.services import storage_service
from backend.src.api.v1.deps import get_current_user, require_role
from backend.src.config import settings

router = APIRouter(prefix="/moderation", tags=["moderation"])

_moderator_or_admin = require_role([UserRole.MODERATOR, UserRole.ADMIN])


@router.post("/reports", response_model=ReportOut, status_code=201)
async def create_report(
    data: ReportCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Любой авторизованный пользователь может пожаловаться на видео."""
    from sqlalchemy import select
    from backend.src.models.channel import Channel

    video = await session.get(Video, data.video_id)
    if not video:
        raise HTTPException(404, "Видео не найдено")

    # Проверка: автор не может жаловаться на свое видео
    channel = await session.get(Channel, video.channel_id)
    if channel and channel.owner_id == user.id:
        raise HTTPException(400, "Нельзя подать жалобу на своё собственное видео")

    # Защита от спама: проверяем нет ли уже активной жалобы от этого пользователя
    existing = await session.execute(
        select(Report).where(
            Report.video_id == data.video_id,
            Report.reporter_id == user.id,
            Report.status == ReportStatus.PENDING,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Вы уже отправили жалобу на это видео, она ожидает рассмотрения")

    report = Report(
        video_id=data.video_id,
        reporter_id=user.id,
        reason=data.reason,
        description=data.description,
    )
    session.add(report)
    await session.flush()
    return _map_report(report, video_title=video.title, reporter_username=user.username)


@router.get("/reports", response_model=list[ReportOut])
async def list_reports(
    status_filter: ReportStatus = ReportStatus.PENDING,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(_moderator_or_admin),
):
    """Список жалоб для панели модератора с фильтром по статусу."""
    result = await session.execute(
        select(Report)
        .where(Report.status == status_filter)
        .options(
            joinedload(Report.video),
            joinedload(Report.reporter),
        )
        .order_by(Report.created_at.asc())
    )
    reports = result.scalars().all()
    return [
        _map_report(
            r,
            video_title=r.video.title if r.video else None,
            reporter_username=r.reporter.username if r.reporter else None,
        )
        for r in reports
    ]


@router.post("/reports/{report_id}/resolve", response_model=ReportOut)
async def resolve_report(
    report_id: int,
    data: ReportResolveRequest,
    session: AsyncSession = Depends(get_db),
    moderator: User = Depends(_moderator_or_admin),
):
    """
    Разрешение жалобы:
    - hide    → скрыть видео (is_hidden_by_mod = True, статус RESOLVED)
    - dismiss → отклонить жалобу (статус DISMISSED)
    - delete  → удалить видео из S3 и БД (только ADMIN)
    """
    report = await session.get(Report, report_id)
    if not report:
        raise HTTPException(404)
    if report.status != ReportStatus.PENDING:
        raise HTTPException(409, "Жалоба уже рассмотрена")

    video = await session.get(Video, report.video_id)

    if data.action == "hide":
        if video:
            await session.execute(
                update(Video).where(Video.id == video.id).values(is_hidden_by_mod=True)
            )
        report.status = ReportStatus.RESOLVED

    elif data.action == "dismiss":
        report.status = ReportStatus.DISMISSED

    elif data.action == "delete":
        if moderator.role != UserRole.ADMIN:
            raise HTTPException(403, "Удаление видео — только Admin")
        report.status = ReportStatus.RESOLVED
        report.moderator_id = moderator.id
        report.moderator_notes = data.moderator_notes
        report.resolved_at = datetime.now(timezone.utc)
        out_report = _map_report(
            report,
            video_title=video.title if video else None,
            moderator_username=moderator.username,
        )
        if video:
            await storage_service.delete_object(settings.MINIO_BUCKET_VIDEOS, video.video_s3_key)
            if video.thumbnail_s3_key:
                await storage_service.delete_object(settings.MINIO_BUCKET_THUMBNAILS, video.thumbnail_s3_key)
            await session.delete(video)
        await session.flush()
        return out_report

    report.moderator_id = moderator.id
    report.moderator_notes = data.moderator_notes
    report.resolved_at = datetime.now(timezone.utc)

    await session.flush()
    return _map_report(report, moderator_username=moderator.username)


def _map_report(
    r: Report,
    video_title: str | None = None,
    reporter_username: str | None = None,
    moderator_username: str | None = None,
) -> ReportOut:
    return ReportOut(
        id=r.id,
        video_id=r.video_id,
        reporter_id=r.reporter_id,
        reason=r.reason,
        description=r.description,
        status=r.status,
        moderator_id=r.moderator_id,
        moderator_notes=r.moderator_notes,
        resolved_at=r.resolved_at,
        created_at=r.created_at,
        video_title=video_title,
        reporter_username=reporter_username,
        moderator_username=moderator_username,
    )

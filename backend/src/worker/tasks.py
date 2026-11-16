"""
Celery Tasks — FFmpeg: извлечение метаданных, генерация WebP thumbnail, обновление статуса.
"""

import asyncio
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

from backend.src.worker.celery_app import celery_app
from backend.src.config import settings


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    """Запускает subprocess и выбрасывает RuntimeError при ненулевом коде."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nstderr: {result.stderr}")
    return result


def _get_duration(video_path: str) -> int:
    """Извлекает длительность видео в секундах через ffprobe с безопасным fallback."""
    try:
        result = _run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            video_path,
        ])
        data = json.loads(result.stdout)
        dur = data.get("format", {}).get("duration")
        return int(float(dur)) if dur else 0
    except Exception:
        return 0


def _generate_thumbnail(video_path: str, out_path: str, timestamp: float = 1.0) -> None:
    """Генерирует WebP превью из кадра на заданном времени."""
    _run([
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", video_path,
        "-vframes", "1",
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
        "-f", "webp",
        out_path,
    ])


def _run_async(coro):
    """Запускает корутину в событийном цикле из синхронного Celery контекста."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="worker.process_video", max_retries=3)
def process_video(self, video_id: int, s3_key: str):
    """
    Основная задача обработки видео:
    1. Скачивает файл из MinIO во временный каталог.
    2. Извлекает длительность через ffprobe.
    3. Генерирует WebP thumbnail.
    4. Загружает thumbnail обратно в MinIO.
    5. Обновляет статус видео на READY в PostgreSQL.
    При ошибке — ставит статус FAILED.
    """
    import aioboto3
    import asyncpg

    async def _process():
        # Импортируем здесь, чтобы не тащить все в глобальный контекст воркера
        from sqlalchemy import update
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from backend.src.models.video import Video, VideoStatus

        engine = create_async_engine(settings.DATABASE_URL, pool_size=1, max_overflow=0)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video_input")
            thumb_path = os.path.join(tmpdir, "thumb.webp")

            session = aioboto3.Session()
            s3_kwargs = dict(
                endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                region_name="us-east-1",
            )

            # 1. Скачиваем видео из MinIO
            async with session.client("s3", **s3_kwargs) as s3:
                await s3.download_file(settings.MINIO_BUCKET_VIDEOS, s3_key, video_path)

            # 2. Метаданные через ffprobe
            duration = _get_duration(video_path)

            # 3. Thumbnail
            thumb_timestamp = min(1.0, duration / 2)
            _generate_thumbnail(video_path, thumb_path, thumb_timestamp)

            # 4. Загружаем thumbnail в MinIO
            thumb_key = f"thumbnails/{video_id}_{uuid.uuid4().hex[:8]}.webp"
            async with session.client("s3", **s3_kwargs) as s3:
                with open(thumb_path, "rb") as f:
                    await s3.put_object(
                        Bucket=settings.MINIO_BUCKET_THUMBNAILS,
                        Key=thumb_key,
                        Body=f.read(),
                        ContentType="image/webp",
                    )

            # 5. Обновляем запись в БД — READY
            async with session_factory() as db:
                await db.execute(
                    update(Video)
                    .where(Video.id == video_id)
                    .values(
                        status=VideoStatus.READY,
                        duration_seconds=duration,
                        thumbnail_s3_key=thumb_key,
                    )
                )
                await db.commit()

        await engine.dispose()

    try:
        _run_async(_process())
    except Exception as exc:
        is_last_attempt = self.request.retries >= self.max_retries
        if is_last_attempt:
            async def _mark_failed():
                from sqlalchemy import update
                from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
                from backend.src.models.video import Video, VideoStatus

                engine = create_async_engine(settings.DATABASE_URL, pool_size=1, max_overflow=0)
                async with async_sessionmaker(engine, expire_on_commit=False)() as db:
                    await db.execute(
                        update(Video).where(Video.id == video_id).values(status=VideoStatus.FAILED)
                    )
                    await db.commit()
                await engine.dispose()

            _run_async(_mark_failed())
            raise exc

        raise self.retry(exc=exc, countdown=30)

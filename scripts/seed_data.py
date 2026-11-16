#!/usr/bin/env python3
"""
Seed Data Script — автоматическое наполнение базы данных демо-данными.
Создаёт 3 пользователя (admin, moderator, user), каналы, видео и комментарии.
Запускается при первом старте контейнера (entrypoint.sh).
Идемпотентен — повторный запуск ничего не сломает.
"""

import asyncio
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.src.config import settings
from backend.src.models import Base, User, UserRole, Channel, Video, VideoStatus, VideoPrivacy, Comment
from backend.src.services.auth_service import hash_password


SEED_USERS = [
    {"email": "admin@tube.local",     "username": "admin",     "password": "admin123",  "role": UserRole.ADMIN},
    {"email": "moderator@tube.local", "username": "moderator", "password": "mod123",    "role": UserRole.MODERATOR},
    {"email": "user@tube.local",      "username": "user",      "password": "user123",   "role": UserRole.USER},
]

SEED_CHANNELS = [
    {"owner_username": "admin",     "title": "Admin Channel",     "description": "Official admin channel with platform news."},
    {"owner_username": "user",      "title": "My First Channel",  "description": "Just a regular creator sharing stuff."},
]

SEED_COMMENTS = [
    "Great video! Really enjoyed it.",
    "Thanks for sharing this content.",
    "Learned a lot from this, keep it up!",
    "Excellent quality, subscribed!",
    "This is exactly what I was looking for.",
]


def _generate_test_video(output_path: str, duration: int = 7, color: str = "blue") -> None:
    """Генерирует короткий цветной тестовый ролик через ffmpeg."""
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={color}:size=1280x720:rate=30:duration={duration}",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "64k",
        "-movflags", "+faststart",
        output_path,
    ], check=True, capture_output=True)


def _generate_thumbnail(video_path: str, output_path: str) -> None:
    """Генерирует WebP превью из первого кадра."""
    subprocess.run([
        "ffmpeg", "-y",
        "-ss", "1",
        "-i", video_path,
        "-vframes", "1",
        "-vf", "scale=1280:720",
        "-f", "webp",
        output_path,
    ], check=True, capture_output=True)


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # Проверяем идемпотентность — если admin уже есть, пропускаем
        result = await session.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            print("⏭  Seed данные уже существуют, пропускаем.")
            await engine.dispose()
            return

        print("🌱  Создание пользователей...")
        users: dict[str, User] = {}
        for u in SEED_USERS:
            user = User(
                email=u["email"],
                username=u["username"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
            )
            session.add(user)
            users[u["username"]] = user

        await session.flush()
        print(f"   ✅ {len(users)} пользователей создано")

        print("📺  Создание каналов...")
        channels: dict[str, Channel] = {}
        for ch in SEED_CHANNELS:
            channel = Channel(
                owner_id=users[ch["owner_username"]].id,
                title=ch["title"],
                description=ch["description"],
            )
            session.add(channel)
            channels[ch["owner_username"]] = channel

        await session.flush()
        print(f"   ✅ {len(channels)} каналов создано")

        # Загружаем тестовые видео в MinIO
        print("🎬  Генерация и загрузка тестовых видео (FFmpeg + MinIO)...")
        import aioboto3

        s3_session = aioboto3.Session()
        s3_kwargs = dict(
            endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name="us-east-1",
        )

        video_configs = [
            {"title": "Welcome to YouTube Clone",    "color": "0x1a73e8", "duration": 8,  "channel": "admin"},
            {"title": "My First Video Ever",         "color": "0xe53935", "duration": 10, "channel": "user"},
            {"title": "Platform Demo Tour",          "color": "0x43a047", "duration": 6,  "channel": "admin"},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            async with s3_session.client("s3", **s3_kwargs) as s3:
                for idx, cfg in enumerate(video_configs):
                    vid_path = os.path.join(tmpdir, f"video_{idx}.mp4")
                    thumb_path = os.path.join(tmpdir, f"thumb_{idx}.webp")

                    _generate_test_video(vid_path, cfg["duration"], cfg["color"])
                    _generate_thumbnail(vid_path, thumb_path)

                    vid_key = f"videos/{uuid.uuid4().hex}_seed_{idx}.mp4"
                    thumb_key = f"thumbnails/seed_{idx}_{uuid.uuid4().hex[:8]}.webp"

                    with open(vid_path, "rb") as f:
                        await s3.put_object(
                            Bucket=settings.MINIO_BUCKET_VIDEOS,
                            Key=vid_key, Body=f.read(), ContentType="video/mp4"
                        )
                    with open(thumb_path, "rb") as f:
                        await s3.put_object(
                            Bucket=settings.MINIO_BUCKET_THUMBNAILS,
                            Key=thumb_key, Body=f.read(), ContentType="image/webp"
                        )

                    video = Video(
                        channel_id=channels[cfg["channel"]].id,
                        title=cfg["title"],
                        description=f"Seed video #{idx + 1} — demo content.",
                        video_s3_key=vid_key,
                        thumbnail_s3_key=thumb_key,
                        duration_seconds=cfg["duration"],
                        status=VideoStatus.READY,
                        privacy=VideoPrivacy.PUBLIC,
                    )
                    session.add(video)
                    await session.flush()

                    # Добавляем комментарии
                    for i, text in enumerate(SEED_COMMENTS[:3]):
                        commenter = list(users.values())[i % len(users)]
                        session.add(Comment(
                            video_id=video.id,
                            user_id=commenter.id,
                            text=text,
                        ))

                    print(f"   ✅ [{idx+1}/3] {cfg['title']}")

        await session.commit()
        print("\n🎉  Seed завершён успешно!")
        print("   👤  admin / Admin123!")
        print("   👤  moderator / Moder123!")
        print("   👤  user / User1234!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())

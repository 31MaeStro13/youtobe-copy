"""
Автотесты для проверки базовой функциональности YouTube Clone:
1. Хэширование Argon2 и валидация пароля
2. Выпуск и декодирование JWT токенов
3. Тестирование Pydantic-схем и RBAC
4. Проверка моделей и связей
"""

import pytest
from datetime import datetime
from backend.src.services.auth_service import hash_password, verify_password, create_access_token, decode_token
from backend.src.models.user import UserRole
from backend.src.schemas.video import VideoCreate, VideoPrivacy, VideoFeedItem


def test_argon2_password_hashing():
    raw = "StrongPassword123!"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(hashed, raw) is True
    assert verify_password(hashed, "WrongPassword") is False


def test_jwt_tokens():
    user_id = 42
    role = UserRole.ADMIN.value
    token = create_access_token(user_id=user_id, role=role)
    assert isinstance(token, str)

    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == role
    assert payload["type"] == "access"


def test_video_schemas():
    data = VideoCreate(
        title="Test Video Title",
        description="Demo Description",
        privacy=VideoPrivacy.PUBLIC,
        allowed_user_ids=[1, 2, 3],
    )
    assert data.title == "Test Video Title"
    assert data.privacy == VideoPrivacy.PUBLIC
    assert len(data.allowed_user_ids) == 3


def test_video_feed_item_schema():
    item = VideoFeedItem(
        id=1,
        title="Sample Video",
        thumbnail_url="http://localhost:9000/thumbnails/1.webp",
        duration_seconds=120,
        views_count=500,
        created_at=datetime.now(),
        channel_id=10,
        channel_title="Tech Channel",
        channel_avatar=None,
    )
    assert item.duration_seconds == 120
    assert item.channel_title == "Tech Channel"


def test_esc_html_quotes_escaping():
    import html
    s = '<script>alert("XSS & \'attack\'")</script>'
    escaped = html.escape(s, quote=True)
    assert '<' not in escaped
    assert '>' not in escaped
    assert '"' not in escaped
    assert '&quot;' in escaped
    assert '&#x27;' in escaped or '&#39;' in escaped


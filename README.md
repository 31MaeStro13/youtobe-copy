# YouTube Clone (Fullstack Async Video Platform)

Высокопроизводительный микросервисный клон YouTube, построенный на базе FastAPI, PostgreSQL 16, MinIO (S3) и Celery с обработкой видео через FFmpeg.

---

## 1. Быстрый старт

```bash
git clone https://github.com/31MaeStro13/youtobe-copy.git
cd youtobe-copy
docker compose up -d
```

После завершения сборки и запуска:
* **Веб-интерфейс YouTube**: [http://localhost:8080](http://localhost:8080)
* **Интерактивная документация Swagger**: [http://localhost:8080/docs](http://localhost:8080/docs)
* **Хранилище S3**: [http://localhost:9000](http://localhost:9000)

> [!NOTE]
> При первом запуске автоматически применяются миграции Alembic и скрипт `scripts/seed_data.py` предзаполняет базу данных пользователями, каналами, комментариями и тестовыми видео.

---

## 2. Предзаполненные тестовые учетные записи (RBAC)

| Роль | Логин / Email | Пароль | Доступные действия |
|---|---|---|---|
| **Admin** | `admin` (`admin@tube.local`) | `admin123` | Полный доступ, модерация, удаление любых видео |
| **Moderator** | `moderator` (`moderator@tube.local`) | `mod123` | Панель модерации (`/moderation.html`), скрытие видео |
| **User** | `user` (`user@tube.local`) | `user123` | Загрузка видео, создание канала, лайки, комментарии |

---

## 3. Архитектурный стек
* **Backend**: FastAPI (Python 3.12+), SQLAlchemy 2.0 (async), asyncpg, Pydantic v2, Alembic.
* **Storage**: MinIO (S3 API). Приватные и публичные бакеты, Presigned URLs с ограниченным TTL.
* **Video Streaming**: HTTP Range requests (код 206 Partial Content) для мгновенной перемотки видео.
* **Background Processing**: Celery + Redis + FFmpeg (генерация WebP превью, извлечение таймингов, faststart).
* **Frontend**: 7 экранов под фирменный стиль YouTube (темная тема, адаптивная сетка, плеер, кабинет автора).

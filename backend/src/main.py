import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from backend.src.config import settings
from backend.src.api.v1.auth import router as auth_router
from backend.src.api.v1.videos import router as videos_router
from backend.src.api.v1.channels import router as channels_router
from backend.src.api.v1.comments import router as comments_router
from backend.src.api.v1.moderation import router as moderation_router

# Настройка Loguru: цветной структурированный вывод в stdout и ротация в файл
logger.remove()
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    "logs/tube.log",
    rotation="10 MB",
    retention="7 days",
    level="INFO",
    encoding="utf-8",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ext_port = getattr(settings, "EXTERNAL_PORT", 8080)
    banner = f"""
================================================================================
       ▶ YOUTUBE CLONE — СЕРВИС УСПЕШНО ЗАПУЩЕН И ГОТОВ К РАБОТЕ!
================================================================================
  🌐 Web UI (Фронтенд):     http://localhost:{ext_port}
  📚 Swagger Документация:  http://localhost:{ext_port}/api/docs
  🗄  S3 Хранилище (MinIO):  http://localhost:9000
  
  🔑 Тестовые аккаунты (RBAC):
     • Admin:      admin / admin123     (полные права, удаление любых видео)
     • Moderator:  moderator / mod123   (панель модерации, скрытие видео)
     • User:       user / user123       (автор/зритель, загрузка, комменты)
================================================================================
"""
    print(banner, flush=True)
    logger.success("Сервер FastAPI и фоновые процессы инициализированы.")
    yield
    logger.warning("🛑 Завершение работы сервиса YouTube Clone...")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_logger_middleware(request: Request, call_next):
    """Структурированное логирование входящих HTTP-запросов и времени ответа."""
    start_time = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    path = request.url.path
    # Логируем все API запросы и важные события (игнорируем статику CSS/JS с кодом 200)
    if not (path.endswith((".css", ".js", ".ico", ".png", ".webp")) and response.status_code < 400):
        if response.status_code >= 500:
            logger.error(f"[{client_ip}] {request.method} {path} -> {response.status_code} ({duration_ms:.1f}ms)")
        elif response.status_code >= 400:
            logger.warning(f"[{client_ip}] {request.method} {path} -> {response.status_code} ({duration_ms:.1f}ms)")
        else:
            logger.info(f"[{client_ip}] {request.method} {path} -> {response.status_code} ({duration_ms:.1f}ms)")

    return response

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API роутеры
_prefix = "/api/v1"
app.include_router(auth_router, prefix=_prefix)
app.include_router(videos_router, prefix=_prefix)
app.include_router(channels_router, prefix=_prefix)
app.include_router(comments_router, prefix=_prefix)
app.include_router(moderation_router, prefix=_prefix)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Раздаём фронтенд как статику (SPA)
frontend_path = Path("/app/frontend")
if not frontend_path.exists():
    frontend_path = Path(__file__).resolve().parent.parent.parent / "frontend"

if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


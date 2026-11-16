FROM python:3.12-slim

# Установка системных зависимостей (FFmpeg для обработки видео, curl для healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Установка uv для быстрого и детерминированного развертывания зависимостей
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Копируем зависимости
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml

# Копируем исходный код бэкенда, фронтенда и скрипты
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY scripts/ ./scripts/

# Даем права на исполнение скриптов
RUN chmod +x ./scripts/*.sh 2>/dev/null || true

EXPOSE 8000

CMD ["./scripts/entrypoint.sh"]

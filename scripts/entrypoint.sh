#!/bin/sh
set -e

echo "=== [1/4] Проверка готовности базы данных PostgreSQL ==="
until curl -s http://minio:9000/minio/health/live > /dev/null 2>&1; do
  echo "Ожидание MinIO..."
  sleep 1
done

echo "=== [2/4] Применение миграций Alembic ==="
cd /app/backend && alembic upgrade head
cd /app

echo "=== [3/4] Автоматическое наполнение базы демо-данными (Seed) ==="
python3 scripts/seed_data.py || echo "Демо-данные уже инициализированы или пропущены."

echo "=== [4/4] Запуск веб-сервера FastAPI (Uvicorn) ==="
echo ""
echo "========================================================================"
echo " ▶ YouTube Clone запускается на порту ${EXTERNAL_PORT:-8080}..."
echo " Web UI:     http://localhost:${EXTERNAL_PORT:-8080}"
echo " API Docs:   http://localhost:${EXTERNAL_PORT:-8080}/api/docs"
echo "========================================================================"
echo ""
exec uvicorn backend.src.main:app --host 0.0.0.0 --port 8000

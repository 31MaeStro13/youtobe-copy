"""
Storage Service — MinIO S3: upload, HTTP Range streaming (206), Presigned URLs.
"""

from typing import AsyncGenerator, Optional
import aioboto3
from botocore.exceptions import ClientError

from backend.src.config import settings


def _get_session():
    return aioboto3.Session()


def _client_kwargs() -> dict:
    return dict(
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name="us-east-1",
    )


async def upload_file(
    bucket: str,
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> None:
    """Загружает объект в MinIO/S3."""
    session = _get_session()
    async with session.client("s3", **_client_kwargs()) as s3:
        await s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )


async def stream_range(
    bucket: str,
    key: str,
    range_header: Optional[str],
    chunk_size: int = 1024 * 1024,  # 1 MB чанки
) -> AsyncGenerator[tuple[bytes, int, int, int], None]:
    """
    Асинхронный генератор для HTTP 206 Partial Content стриминга.
    Возвращает (chunk, start, end, total_size).
    """
    session = _get_session()
    async with session.client("s3", **_client_kwargs()) as s3:
        # Узнаём размер объекта
        head = await s3.head_object(Bucket=bucket, Key=key)
        total_size = head["ContentLength"]

        # Парсим Range: bytes=START-END
        start = 0
        end = total_size - 1
        if range_header:
            try:
                raw = range_header.replace("bytes=", "")
                parts = raw.split("-")
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if parts[1] else min(start + 5 * 1024 * 1024 - 1, total_size - 1)
            except (ValueError, IndexError):
                start = 0
                end = min(5 * 1024 * 1024 - 1, total_size - 1)
        else:
            # Если Range не передан, отдаем первый 5MB сегмент, предотвращая OOM
            start = 0
            end = min(5 * 1024 * 1024 - 1, total_size - 1)

        end = min(end, total_size - 1)
        byte_range = f"bytes={start}-{end}"

        response = await s3.get_object(
            Bucket=bucket,
            Key=key,
            Range=byte_range,
        )

        async with response["Body"] as stream:
            chunk = await stream.read()
            yield chunk, start, end, total_size


async def generate_presigned_url(
    bucket: str,
    key: str,
    expiration: int = settings.PRESIGNED_URL_EXPIRATION_SECONDS,
) -> str:
    """Генерирует Presigned URL для прямого доступа к объекту с TTL, доступный браузеру извне Docker."""
    session = _get_session()
    async with session.client("s3", **_client_kwargs()) as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiration,
        )
    # Если URL сгенерирован с внутренним хостом minio:9000, заменяем на публичный endpoint для браузера
    if settings.MINIO_ENDPOINT in url and settings.MINIO_PUBLIC_ENDPOINT:
        url = url.replace(f"http://{settings.MINIO_ENDPOINT}", settings.MINIO_PUBLIC_ENDPOINT)
    return url


async def delete_object(bucket: str, key: str) -> None:
    """Удаляет объект из S3/MinIO."""
    session = _get_session()
    async with session.client("s3", **_client_kwargs()) as s3:
        try:
            await s3.delete_object(Bucket=bucket, Key=key)
        except ClientError:
            pass  # объект уже удалён — нас устраивает


async def object_exists(bucket: str, key: str) -> bool:
    session = _get_session()
    async with session.client("s3", **_client_kwargs()) as s3:
        try:
            await s3.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

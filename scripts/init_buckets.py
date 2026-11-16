"""
Скрипт инициализации S3-бакетов (videos, thumbnails) через boto3.
Запускается автоматически в minio-init контейнере.
"""

import os
import sys
import time
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
BUCKETS = [
    os.getenv("MINIO_BUCKET_VIDEOS", "videos"),
    os.getenv("MINIO_BUCKET_THUMBNAILS", "thumbnails"),
]

s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

print(f"Connecting to S3 at {ENDPOINT}...")
for attempt in range(30):
    try:
        s3.list_buckets()
        print("Connected to S3 successfully.")
        break
    except Exception as e:
        print(f"Waiting for S3 ({attempt+1}/30)... error: {e}")
        time.sleep(2)
else:
    print("Failed to connect to S3.")
    sys.exit(1)

for bucket in BUCKETS:
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"Bucket '{bucket}' already exists.")
    except ClientError:
        try:
            s3.create_bucket(Bucket=bucket)
            print(f"Created bucket '{bucket}'.")
        except Exception as e:
            print(f"Error creating bucket '{bucket}': {e}")
            sys.exit(1)

print("S3 initialization completed successfully.")

"""MinIO/S3 wrapper. Используем sync minio SDK через asyncio.to_thread — это ок для нашего объёма."""

from __future__ import annotations

import asyncio
import io
import os
import uuid
from dataclasses import dataclass

from minio import Minio
from minio.error import S3Error


@dataclass
class MinioConfig:
    endpoint: str             # host:port (без http://)
    access_key: str
    secret_key: str
    bucket: str
    secure: bool = False


class MinioStorage:
    def __init__(self, config: MinioConfig) -> None:
        self.bucket = config.bucket
        self._client = Minio(
            config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure,
        )
        self._ensured = False

    async def ensure_bucket(self) -> None:
        if self._ensured:
            return
        def _do() -> None:
            try:
                if not self._client.bucket_exists(self.bucket):
                    self._client.make_bucket(self.bucket)
            except S3Error:
                pass
        await asyncio.to_thread(_do)
        self._ensured = True

    async def put_receipt(self, project_id: int, data: bytes, filename: str | None = None) -> str:
        """Кладёт фото чека и возвращает minio_key (relative path внутри bucket)."""
        await self.ensure_bucket()
        ext = "jpg"
        if filename and "." in filename:
            ext = filename.rsplit(".", 1)[1][:8].lower() or "jpg"
        key = f"receipts/{project_id}/{uuid.uuid4().hex}.{ext}"

        def _do() -> None:
            self._client.put_object(
                self.bucket, key, io.BytesIO(data), length=len(data),
                content_type=f"image/{ext if ext != 'jpg' else 'jpeg'}",
            )
        await asyncio.to_thread(_do)
        return key

    async def get_object(self, key: str) -> bytes:
        def _do() -> bytes:
            resp = self._client.get_object(self.bucket, key)
            try:
                return resp.read()
            finally:
                resp.close()
                resp.release_conn()
        return await asyncio.to_thread(_do)


def build_storage() -> MinioStorage:
    endpoint = os.environ["MINIO_ENDPOINT"]
    # strip scheme if user gave full URL
    if endpoint.startswith("http://"):
        endpoint = endpoint[7:]
        secure = False
    elif endpoint.startswith("https://"):
        endpoint = endpoint[8:]
        secure = True
    else:
        secure = False
    return MinioStorage(
        MinioConfig(
            endpoint=endpoint,
            access_key=os.environ["MINIO_ROOT_USER"],
            secret_key=os.environ["MINIO_ROOT_PASSWORD"],
            bucket=os.environ.get("MINIO_BUCKET", "stager-receipts"),
            secure=secure,
        )
    )

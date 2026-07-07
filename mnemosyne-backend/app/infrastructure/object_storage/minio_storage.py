"""ObjectStoragePort adapter backed by MinIO.

The minio SDK is synchronous; calls are pushed to a thread to keep the
event loop unblocked.
"""

import asyncio
import io
import json
from typing import Any

from minio import Minio

from app.config import get_settings


class MinioStorageAdapter:
    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        secure: bool | None = None,
    ) -> None:
        settings = get_settings()
        self._bucket = bucket or settings.minio_bucket
        self._client = Minio(
            endpoint or settings.minio_endpoint,
            access_key=access_key or settings.minio_access_key,
            secret_key=secret_key or settings.minio_secret_key,
            secure=settings.minio_secure if secure is None else secure,
        )
        self._bucket_checked = False

    def _ensure_bucket_sync(self) -> None:
        if not self._bucket_checked:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
            self._bucket_checked = True

    def _put_sync(self, key: str, payload: Any) -> None:
        self._ensure_bucket_sync()
        data = json.dumps(payload, default=str).encode()
        self._client.put_object(
            self._bucket, key, io.BytesIO(data), len(data), content_type="application/json"
        )

    def _get_sync(self, key: str) -> Any:
        self._ensure_bucket_sync()
        response = self._client.get_object(self._bucket, key)
        try:
            return json.loads(response.read())
        finally:
            response.close()
            response.release_conn()

    async def put_json(self, key: str, payload: Any) -> None:
        await asyncio.to_thread(self._put_sync, key, payload)

    async def get_json(self, key: str) -> Any:
        return await asyncio.to_thread(self._get_sync, key)

"""Integration tests for the MinIO adapter (real MinIO)."""

from uuid import uuid4

from app.infrastructure.object_storage.minio_storage import MinioStorageAdapter
from tests.integration.conftest import MINIO_ENDPOINT


class TestMinioStorage:
    async def test_put_and_get_json_roundtrip(self):
        adapter = MinioStorageAdapter(
            endpoint=MINIO_ENDPOINT,
            access_key="mnemosyne",
            secret_key="mnemosyne-secret",
            bucket="mnemosyne-test",
            secure=False,
        )
        repo_id = uuid4()
        key = f"raw/github/repos/{repo_id}/issues/page-1.json"
        payload = {"items": [{"number": 1, "title": "bug"}], "etag": "abc"}

        await adapter.put_json(key, payload)
        loaded = await adapter.get_json(key)
        assert loaded == payload

    async def test_overwrite_same_key(self):
        adapter = MinioStorageAdapter(
            endpoint=MINIO_ENDPOINT,
            access_key="mnemosyne",
            secret_key="mnemosyne-secret",
            bucket="mnemosyne-test",
            secure=False,
        )
        key = f"snapshots/{uuid4()}/tree.json"
        await adapter.put_json(key, {"v": 1})
        await adapter.put_json(key, {"v": 2})
        assert (await adapter.get_json(key))["v"] == 2

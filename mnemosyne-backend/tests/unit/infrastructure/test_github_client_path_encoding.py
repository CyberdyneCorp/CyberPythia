"""#83 (CWE-22): user-controlled repo/file paths must be URL-encoded before they
are interpolated into GitHub REST URLs, and object-storage keys must reject
`..` traversal segments."""

import pytest
import respx

from app.infrastructure.github.client import (
    GitHubClient,
    _safe_object_key,
    _url_path,
)

BASE = "https://api.github.com"


def test_url_path_encodes_segments_preserving_slashes():
    assert _url_path("owner/repo") == "owner/repo"  # normal input unchanged
    assert _url_path("dir/a b.py") == "dir/a%20b.py"
    assert _url_path("a/../b?x=1#y") == "a/../b%3Fx%3D1%23y"


def test_safe_object_key_rejects_traversal():
    assert _safe_object_key("raw/github/repos/o/r/tree.json").endswith("tree.json")
    with pytest.raises(ValueError):
        _safe_object_key("raw/github/repos/../../etc/passwd")


@respx.mock
async def test_get_file_content_encodes_special_path():
    route = respx.get(
        f"{BASE}/repos/cyberdyne/a/contents/dir/a%20b.py"
    ).respond(200, json={"content": "hi", "encoding": "utf-8"})

    client = GitHubClient(base_url=BASE)
    await client.get_file_content("t", "cyberdyne/a", "dir/a b.py")

    assert route.called  # raw space would have hit a different (unmatched) URL


async def test_snapshot_rejects_traversing_key():
    class _Storage:
        def __init__(self):
            self.keys = []

        async def put_json(self, key, payload):
            self.keys.append(key)

    storage = _Storage()
    client = GitHubClient(base_url=BASE, storage=storage)

    with pytest.raises(ValueError):
        await client._snapshot("raw/github/repos/../../etc/passwd.json", {"a": 1})
    assert storage.keys == []  # nothing written under a traversing key

"""#71 (CWE-918): the GitHub client must not follow a `Link: rel=next` URL to
another or internal host (which would leak the bearer token off-allowlist)."""

import respx

from app.infrastructure.github.client import GitHubClient

BASE = "https://api.github.com"


@respx.mock
async def test_paginate_refuses_offsite_next_link():
    respx.get(f"{BASE}/things").respond(
        200,
        json=[{"n": 1}],
        headers={"Link": '<https://169.254.169.254/evil?page=2>; rel="next"'},
    )
    internal = respx.get("https://169.254.169.254/evil").respond(200, json=[{"n": 2}])

    client = GitHubClient(base_url=BASE)
    items = await client._paginate("/things", "secret-token")

    assert items == [{"n": 1}]  # stopped after page 1
    assert internal.call_count == 0  # internal host never requested; token not sent


@respx.mock
async def test_paginate_refuses_different_public_host():
    respx.get(f"{BASE}/things").respond(
        200,
        json=[{"n": 1}],
        headers={"Link": '<https://evil.example/repos?page=2>; rel="next"'},
    )
    evil = respx.get("https://evil.example/repos").respond(200, json=[{"n": 2}])

    client = GitHubClient(base_url=BASE)
    items = await client._paginate("/things", "secret-token")

    assert items == [{"n": 1}]
    assert evil.call_count == 0


@respx.mock
async def test_paginate_follows_same_origin_next_link():
    respx.get(f"{BASE}/things").respond(
        200,
        json=[{"n": 1}],
        headers={"Link": f'<{BASE}/things_page2>; rel="next"'},
    )
    respx.get(f"{BASE}/things_page2").respond(200, json=[{"n": 2}])

    client = GitHubClient(base_url=BASE)
    items = await client._paginate("/things", "secret-token")

    assert items == [{"n": 1}, {"n": 2}]

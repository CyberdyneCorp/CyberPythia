"""Unit tests for the shared SSRF URL guard (#71/#78/#79, CWE-918)."""

import pytest

from app.infrastructure.security.url_guard import (
    UnsafeUrlError,
    assert_public_https_url,
    is_allowed_follow_url,
)


def test_public_https_url_accepted():
    assert_public_https_url("https://api.github.com/repos")
    assert_public_https_url("https://hooks.slack.com/services/abc")


@pytest.mark.parametrize(
    "url",
    [
        "http://api.github.com",  # not https
        "https://169.254.169.254/latest/meta-data/",  # cloud metadata (link-local)
        "https://127.0.0.1/",  # loopback
        "https://10.0.0.5/",  # RFC1918
        "https://192.168.1.1/",  # RFC1918
        "https://172.16.0.1/",  # RFC1918
        "https://localhost/",  # loopback name
        "https://[::1]/",  # IPv6 loopback
        "ftp://example.com/",  # non-http scheme
        "https:///no-host",  # no host
    ],
)
def test_unsafe_urls_rejected(url):
    with pytest.raises(UnsafeUrlError):
        assert_public_https_url(url)


def test_localhost_exception_opt_in():
    # Rejected by default, allowed when explicitly permitted (dev/test).
    with pytest.raises(UnsafeUrlError):
        assert_public_https_url("http://localhost:8000/hook")
    assert_public_https_url("http://localhost:8000/hook", allow_localhost=True)
    assert_public_https_url("http://127.0.0.1:9000/hook", allow_localhost=True)


def test_localhost_exception_still_blocks_nonlocal_internal():
    # The dev exception must not open the door to other internal ranges.
    with pytest.raises(UnsafeUrlError):
        assert_public_https_url("https://169.254.169.254/", allow_localhost=True)


def test_follow_url_same_origin_allowed():
    base = "https://api.github.com"
    assert is_allowed_follow_url("https://api.github.com/repositories?page=2", base)


@pytest.mark.parametrize(
    "candidate",
    [
        "https://evil.example/repos?page=2",  # different host
        "https://169.254.169.254/latest",  # internal host
        "http://api.github.com/repos?page=2",  # downgraded scheme
        "https://api.github.com:8443/x",  # different port
    ],
)
def test_follow_url_off_allowlist_rejected(candidate):
    assert not is_allowed_follow_url(candidate, "https://api.github.com")

"""Shared SSRF guard for outbound URLs (CWE-918).

One helper reused by every place the app follows or POSTs to an externally
influenced URL (GitHub pagination `Link` headers, the alert webhook, the
configured GitHub API base). It rejects non-HTTPS schemes and hosts that are —
or resolve to — loopback, link-local, private (RFC1918), or otherwise
non-public addresses, so a hostile or misconfigured URL can't reach internal
services such as the cloud metadata endpoint (169.254.169.254). A dev/test
localhost exception is opt-in for local development only.
"""

import ipaddress
import socket
from urllib.parse import urlsplit

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class UnsafeUrlError(ValueError):
    """A URL failed the SSRF host guard."""


def _parse_ip(host: str) -> IPAddress | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _resolve(host: str) -> list[IPAddress]:
    """Best-effort DNS resolution. Returns [] when the host can't be resolved so
    legitimate public hosts still validate when the runner is offline; blocked
    ranges are still caught for IP literals and resolvable internal names."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return []
    addrs: list[IPAddress] = []
    for info in infos:
        sockaddr = info[4]
        ip = _parse_ip(str(sockaddr[0]))
        if ip is not None:
            addrs.append(ip)
    return addrs


def _is_blocked_ip(ip: IPAddress) -> bool:
    return (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_private
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_public_https_url(url: str, *, allow_localhost: bool = False) -> None:
    """Raise `UnsafeUrlError` unless `url` is an https URL to a public host.

    With `allow_localhost=True` (dev/test only) a loopback host is permitted and
    the scheme may be http, so a local Slack-compatible receiver can be used.
    """
    parts = urlsplit(url)
    host = parts.hostname
    if not host:
        raise UnsafeUrlError(f"URL has no host: {url!r}")

    lowered = host.lower()
    literal = _parse_ip(host)
    is_local = (
        lowered == "localhost"
        or lowered.endswith(".localhost")
        or (literal is not None and literal.is_loopback)
    )

    if parts.scheme != "https" and not (
        allow_localhost and parts.scheme == "http" and is_local
    ):
        raise UnsafeUrlError(f"URL must use https: {url!r}")

    if is_local:
        if allow_localhost:
            return
        raise UnsafeUrlError(f"localhost is not an allowed host: {url!r}")

    candidates = [literal] if literal is not None else _resolve(host)
    for ip in candidates:
        if _is_blocked_ip(ip):
            raise UnsafeUrlError(f"URL host resolves to a blocked address {ip}: {url!r}")


def is_allowed_follow_url(url: str, base_url: str) -> bool:
    """Whether a pagination `Link` URL may be followed with the API bearer token.

    Only same-origin https URLs (identical host/port as the configured API base)
    are allowed, so an upstream-controlled `Link: rel=next` header can't redirect
    the authenticated request — and its bearer token — to another or internal
    host (CWE-918)."""
    candidate = urlsplit(url)
    base = urlsplit(base_url)
    if candidate.scheme != "https":
        return False
    if candidate.hostname is None or base.hostname is None:
        return False
    if candidate.hostname.lower() != base.hostname.lower():
        return False
    return candidate.port == base.port

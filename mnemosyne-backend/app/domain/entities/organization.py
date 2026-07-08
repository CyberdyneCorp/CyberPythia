"""GitHub organization sync-scope entity (spec: github-connection)."""

from dataclasses import dataclass


@dataclass(slots=True)
class Organization:
    login: str
    sync_enabled: bool = True

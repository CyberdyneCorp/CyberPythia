"""Parsed GitHub webhook delivery (spec: webhooks)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class WebhookEvent:
    delivery_id: str
    event: str  # X-GitHub-Event header, e.g. "push", "issues"
    action: str | None  # payload.action when present
    installation_id: str | None  # payload.installation.id
    repository_full_name: str | None  # payload.repository.full_name
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def issue_number(self) -> int | None:
        issue = self.payload.get("issue")
        return issue.get("number") if isinstance(issue, dict) else None

    @property
    def pull_request_number(self) -> int | None:
        for key in ("pull_request", "issue"):
            node = self.payload.get(key)
            if isinstance(node, dict) and "number" in node:
                return int(node["number"])
        return None

    @property
    def repository_deleted(self) -> bool:
        return self.event == "repository" and self.action == "deleted"

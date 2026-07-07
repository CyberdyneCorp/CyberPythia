"""Map a webhook event to an incremental-sync intent (spec: webhooks; design D4).

Pure: no I/O. The processor executes the returned intent.
"""

from app.domain.entities.webhook_event import WebhookEvent
from app.domain.value_objects.enums import WebhookIntent

_ISSUE_EVENTS = frozenset({"issues", "issue_comment"})
_PR_EVENTS = frozenset(
    {"pull_request", "pull_request_review", "pull_request_review_comment"}
)


def route(event: WebhookEvent) -> WebhookIntent:
    if event.event == "push":
        return WebhookIntent.SYNC_REPOSITORY
    if event.event in _ISSUE_EVENTS:
        # issue_comment on a PR-flavored issue is a PR event
        if event.event == "issue_comment" and _is_pull_request_comment(event):
            return WebhookIntent.SYNC_PULL_REQUEST
        return WebhookIntent.SYNC_ISSUE if event.issue_number else WebhookIntent.IGNORE
    if event.event in _PR_EVENTS:
        return (
            WebhookIntent.SYNC_PULL_REQUEST
            if event.pull_request_number
            else WebhookIntent.IGNORE
        )
    if event.event == "repository":
        if event.repository_deleted:
            return WebhookIntent.REMOVE_REPOSITORY
        return WebhookIntent.UPDATE_REPOSITORY
    if event.event in ("installation", "installation_repositories"):
        return WebhookIntent.RECONCILE_INSTALLATION
    return WebhookIntent.IGNORE


def _is_pull_request_comment(event: WebhookEvent) -> bool:
    issue = event.payload.get("issue")
    return isinstance(issue, dict) and "pull_request" in issue

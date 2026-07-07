from app.domain.entities.webhook_event import WebhookEvent
from app.domain.services.webhook_router import route
from app.domain.value_objects.enums import WebhookIntent


def event(evt, action=None, payload=None):
    return WebhookEvent(
        delivery_id="d1", event=evt, action=action,
        installation_id="123", repository_full_name="cyberdyne/a",
        payload=payload or {},
    )


class TestRoute:
    def test_push(self):
        assert route(event("push")) is WebhookIntent.SYNC_REPOSITORY

    def test_issue(self):
        e = event("issues", "opened", {"issue": {"number": 42}})
        assert route(e) is WebhookIntent.SYNC_ISSUE

    def test_issue_comment_on_issue(self):
        e = event("issue_comment", "created", {"issue": {"number": 42}})
        assert route(e) is WebhookIntent.SYNC_ISSUE

    def test_issue_comment_on_pull_request(self):
        e = event("issue_comment", "created", {"issue": {"number": 7, "pull_request": {}}})
        assert route(e) is WebhookIntent.SYNC_PULL_REQUEST

    def test_issue_without_number_ignored(self):
        assert route(event("issues", "labeled", {})) is WebhookIntent.IGNORE

    def test_pull_request(self):
        e = event("pull_request", "opened", {"pull_request": {"number": 61}})
        assert route(e) is WebhookIntent.SYNC_PULL_REQUEST

    def test_pull_request_review(self):
        e = event("pull_request_review", "submitted", {"pull_request": {"number": 61}})
        assert route(e) is WebhookIntent.SYNC_PULL_REQUEST

    def test_repository_updated(self):
        assert route(event("repository", "renamed")) is WebhookIntent.UPDATE_REPOSITORY

    def test_repository_deleted(self):
        assert route(event("repository", "deleted")) is WebhookIntent.REMOVE_REPOSITORY

    def test_installation(self):
        assert route(event("installation", "created")) is WebhookIntent.RECONCILE_INSTALLATION
        assert (
            route(event("installation_repositories", "added"))
            is WebhookIntent.RECONCILE_INSTALLATION
        )

    def test_unknown_event_ignored(self):
        assert route(event("star", "created")) is WebhookIntent.IGNORE

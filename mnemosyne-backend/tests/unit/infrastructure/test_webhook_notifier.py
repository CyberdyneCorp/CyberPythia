"""#78 (CWE-918): the alert webhook sink is validated at construction."""

import pytest

from app.infrastructure.notify.webhook_notifier import WebhookNotifier
from app.infrastructure.security.url_guard import UnsafeUrlError


def test_none_url_is_allowed():
    notifier = WebhookNotifier(None)
    assert notifier.configured is False


def test_public_https_url_is_allowed():
    notifier = WebhookNotifier("https://hooks.slack.com/services/abc")
    assert notifier.configured is True


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata (IMDS)
        "https://10.0.0.5/hook",  # RFC1918
        "http://localhost:9000/hook",  # loopback (no dev exception)
        "http://internal-service/hook",  # not https
    ],
)
def test_internal_or_insecure_url_rejected(url):
    with pytest.raises(UnsafeUrlError):
        WebhookNotifier(url)


def test_localhost_allowed_in_dev():
    notifier = WebhookNotifier("http://localhost:9000/hook", allow_localhost=True)
    assert notifier.configured is True

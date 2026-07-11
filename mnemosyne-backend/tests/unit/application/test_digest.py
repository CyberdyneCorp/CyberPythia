"""Attention digest assembly + best-effort webhook delivery (spec: engineering-intelligence)."""

from types import SimpleNamespace

import httpx
import respx

from app.application.use_cases.digest import DigestService
from app.infrastructure.notify.webhook_notifier import WebhookNotifier


class _Readiness:
    def __init__(self, regs):
        self._regs = regs

    async def organization_regressions(self, org):
        return {"regressions": self._regs}


class _CrossRepo:
    def __init__(self, issues, prs):
        self._issues, self._prs = issues, prs

    async def find_stale_issues(self, *, organization, limit):
        return self._issues

    async def find_stale_prs(self, *, organization, limit):
        return self._prs


class _Delivery:
    def __init__(self, at_risk):
        self._at_risk = at_risk

    async def delivery_scorecard(self, now=None, organization=None):
        return [SimpleNamespace(at_risk_milestones=self._at_risk)]


def _svc(regs=None, issues=None, prs=None, at_risk=0):
    return DigestService(
        _Readiness(regs or []), _CrossRepo(issues or [], prs or []), _Delivery(at_risk)
    )


async def test_digest_assembles_sections_and_summary():
    d = await _svc(
        regs=[{"full_name": "o/a", "from_gate": "READY", "to_gate": "MVP"}],
        issues=[{"number": 1}], prs=[], at_risk=2,
    ).build("CyberdyneCorp")
    assert d["is_empty"] is False
    assert d["at_risk_milestones"] == 2
    assert len(d["regressions"]) == 1 and len(d["stale_issues"]) == 1
    assert "1 readiness regression(s)" in d["summary"]
    assert d["text"] == d["summary"]  # Slack-compatible


async def test_digest_empty_when_no_signals():
    d = await _svc().build("CyberdyneCorp")
    assert d["is_empty"] is True


async def test_notifier_returns_false_without_url():
    assert (await WebhookNotifier(None).send({"text": "hi"})) is False
    assert WebhookNotifier(None).configured is False


@respx.mock
async def test_notifier_posts_and_reports_success():
    route = respx.post("https://hooks.example/x").mock(return_value=httpx.Response(200))
    ok = await WebhookNotifier("https://hooks.example/x").send({"text": "hi"})
    assert ok is True and route.called


@respx.mock
async def test_notifier_swallows_delivery_errors():
    respx.post("https://hooks.example/x").mock(return_value=httpx.Response(500))
    assert (await WebhookNotifier("https://hooks.example/x").send({"text": "hi"})) is False

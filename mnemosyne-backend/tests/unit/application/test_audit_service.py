from app.application.audit import AuditService
from app.domain.value_objects.identity import CallerIdentity


class FakeAuditPort:
    def __init__(self):
        self.records = []

    async def record(self, entry):
        self.records.append(entry)

    async def list_recent(self, limit=100):
        return self.records[-limit:]


async def test_record_with_caller():
    port = FakeAuditPort()
    service = AuditService(port)
    caller = CallerIdentity(subject="user-1", client_id="web")
    await service.record(caller, "github.connect", target="cyberdyne")

    entry = port.records[0]
    assert entry.subject == "user-1"
    assert entry.client_id == "web"
    assert entry.operation == "github.connect"
    assert entry.target == "cyberdyne"
    assert entry.outcome == "ok"
    assert entry.occurred_at.tzinfo is not None


async def test_record_denied_anonymous():
    port = FakeAuditPort()
    service = AuditService(port)
    await service.record_denied(None, "access.GET /api/v1/repos")

    entry = port.records[0]
    assert entry.subject == "anonymous"
    assert entry.outcome == "denied"

# Tasks

- [x] 1. `NotifierPort` + HTTP webhook adapter (POST JSON, best-effort)
- [x] 2. `DigestService.build(org)` reusing readiness + cross-repo stale + delivery milestones
- [x] 3. Config: alert_webhook_url, alert_digest_enabled
- [x] 4. Composition wiring
- [x] 5. Worker: daily digest send after readiness recording (best-effort)
- [x] 6. REST: /organizations/{org}/digest
- [x] 7. MCP: get_organization_digest
- [x] 8. Tests: digest assembly, notifier, worker delivery best-effort, endpoint/tool

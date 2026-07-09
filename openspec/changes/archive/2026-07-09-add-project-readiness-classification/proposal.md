# Add project readiness classification (MVP / READY / DONE)

## Why

Amini's engineering phase gates (MVP/Alpha → Ready/Beta → Done/GA) are applied by
hand today. Mnemosyne already extracts the signals that most of the gate criteria
map to (CI, tests, OpenSpec, issues/PRs, docs, dependency/security hygiene), so it
can classify every indexed repository automatically and show owners exactly what a
project is missing to advance.

## What changes

- A readiness classifier maps **observable** GitHub signals to a gate:
  - **MVP** — a synced repo that hasn't met READY.
  - **READY** — CI + tests + documented design (OpenSpec or ADRs) + real workflow
    evidence (≥1 closed issue and ≥1 merged PR) + README + a guide doc.
  - **DONE** — READY + dependency manifest + monitoring (Dependabot or a security-
    scanning workflow) + a SECURITY doc + a low open-bug ratio.
  Each check reports `met` / `missing` / `unknown` (unknown = the signal needs a
  code-indexing mode that captures the file tree).
- Two new file signals: `has_dependabot`, `has_security_scanning` (CodeQL/Semgrep/
  Trivy/Snyk workflows).
- MCP: `mnemosyne_get_repository_readiness`, `mnemosyne_get_organization_readiness`.
- REST: `GET /api/v1/repos/{id}/readiness`,
  `GET /api/v1/intelligence/organizations/{org}/readiness`.
- Web: a readiness distribution + per-repo gate badges on the Intelligence page.

## Impact

- Affected specs: `engineering-intelligence`, `mcp-interface`, `rest-api`, `web-ui`.
- Affected code: pure `classify_readiness` + `ReadinessService`; extended
  `RepositorySignalsService`; MCP tools; REST endpoints; SvelteKit Intelligence view.
- Read-only, additive. **Observable-only, strict**: only GitHub signals decide the
  gate; org-process criteria (SLA, DR, on-call, pen-test) are out of scope for the
  automated gate. CI/tests/monitoring require a file-tree indexing mode
  (`code_metadata`+); repos without it report those checks as `unknown`.

## Non-goals / follow-ups

- GitHub Releases as an additional DONE signal (not yet indexed).
- Manual attestation of SLA/DR/on-call/pen-test (a later "declared gate" overlay).

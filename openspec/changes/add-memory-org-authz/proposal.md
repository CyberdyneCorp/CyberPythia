# Enforce per-org authorization in the agent-memory subsystem

## Why

The per-organization authorization boundary (change `add-per-organization`) is
wired only into the repository store choke point. The agent-memory subsystem's
organization dimension and delete-by-id path never consult it, so a caller
scoped to one organization can reach another organization's memories:

- Organization recall (`GET /api/v1/intelligence/organizations/{org}/memories`,
  MCP `mnemosyne_recall`) lists any org's memories with no scope check
  (BOLA / CWE-639).
- Organization remember (`POST .../memories`, MCP `mnemosyne_remember`) writes
  into an arbitrary org namespace with no scope check (CWE-284).
- Forget (`DELETE /api/v1/repos/{repo_id}/memories/{memory_id}`,
  MCP `mnemosyne_forget`) deletes by bare primary key with no ownership check
  (IDOR / CWE-639); chained with recall it deletes memories cross-org.

Repository-scoped recall/remember already resolve the repository through the
scoped store, so they are safe; only the organization dimension and the
delete-by-id path bypass the boundary.

## What changes

- Organization recall and remember gate on
  `org_scope.is_organization_allowed(organization)`; a disallowed organization
  raises the not-found error (mirrors how an out-of-scope repository 404s).
- Forget loads the memory, resolves its owner (repository → organization for
  repository-scoped memories, or the `organization` field for org-scoped
  memories), and verifies access before deleting; an out-of-scope or unknown
  memory reads as not found. It never deletes by bare id.
- Defense-in-depth: the memory store's `list_for_organization` (Postgres adapter
  and the in-memory fake) returns empty for an out-of-scope organization even if
  the use-case gate is bypassed.
- The organization-memory REST endpoints translate the not-found error to 404
  (they previously returned it untranslated).

Non-goals: changing the org-scope contextvar's unrestricted default
(FINDING-025 / #76); per-memory ACLs beyond the organization boundary.

## Impact

- Affected specs: `agent-memory` (recall/remember/forget become org-scoped).
- Affected code: `app/application/use_cases/memory.py`,
  `app/infrastructure/persistence/repositories/misc.py`
  (`PostgresMemoryRepository.list_for_organization`),
  `app/interfaces/api/routers/intelligence.py` (error translation),
  `tests/unit/application/fakes.py` (`FakeMemoryPort`).
- Security: closes cross-org read (#52), write (#53), and delete (#54) on
  agent memories.

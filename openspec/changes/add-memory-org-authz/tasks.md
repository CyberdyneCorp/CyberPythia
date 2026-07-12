# Tasks

- [x] 1. Gate `recall_organization` / `remember_organization` on
      `is_organization_allowed`; raise `UnknownResourceError` when disallowed
- [x] 2. Rewrite `forget` to load the memory, resolve its owner, and check org
      scope before deleting (never delete by bare id)
- [x] 3. Defense-in-depth: `list_for_organization` returns empty for an
      out-of-scope org (Postgres adapter + `FakeMemoryPort`)
- [x] 4. Translate the not-found error to 404 in the organization-memory REST
      endpoints
- [x] 5. Tests: use-case cross-org recall/remember/forget denied, same-org and
      unrestricted callers allowed; API-level scoped-caller 404 on another org's
      memories

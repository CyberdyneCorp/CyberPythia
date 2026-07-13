# Tasks

- [x] 1. Add `authorized_org_logins` to `CallerIdentity`; `allowed_organizations` prefers it (empty = deny-all; admin unrestricted), else falls back to the plan-qualifier derivation
- [x] 2. Parse the `orgs` claim into GitHub logins in `_identity_from_claims` (JWKS + introspection), null `github_login` omitted, absent → `None`
- [x] 3. Regression tests: claim present restricts to logins; empty claim denies all; claim overrides a real plan qualifier; admin still unrestricted; absent falls back to entitlements; claim parsing (lowercase/null/empty/absent)
- [x] 4. Update the auth spec (`Per-organization access scoping`) to make the `orgs` claim authoritative with the entitlement derivation as legacy fallback

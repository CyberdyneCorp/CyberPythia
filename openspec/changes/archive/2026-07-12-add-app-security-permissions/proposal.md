# Request security-alert read in the App manifest

## Why

The vulnerability-signals feature reads Dependabot alerts, which needs a GitHub
App's `vulnerability_alerts: read` grant. Apps created by the manifest onboarding
only requested Contents/Issues/Pull-requests/Metadata, so the signal reads
`unknown` until an admin manually adds the permission on GitHub (as just
happened for CyberdyneCorp). Requesting it up front means future installs are
ready for security intelligence without a manual permission edit.

## What changes

The App manifest's `default_permissions` additionally request read-only
`vulnerability_alerts` (Dependabot alerts) and `security_events` (code scanning).
All grants remain read-only. Existing Apps are unaffected; this only changes what
new "Create App" onboarding requests.

## Impact

- `build_app_manifest` default permissions (+2 read scopes).
- github-connection spec: manifest onboarding permission list.

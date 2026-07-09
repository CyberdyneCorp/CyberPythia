# One-click GitHub App onboarding (manifest flow)

## Why

Installing the GitHub App today is a manual, error-prone hand-off: an admin creates
the App in GitHub's UI (setting permissions, events, webhook URL + secret by hand),
generates a private key, installs it, then copy-pastes the App ID, installation ID,
PEM, and secret into Mnemosyne's registration form. Only that last step is on our
dashboard. GitHub provides an **App Manifest flow** that lets an application create a
correctly-configured App with a single hand-off and receive its credentials back
automatically — turning a ~10-minute manual chore into two clicks.

## What changes

- The dashboard gains a **"Create GitHub App" button** that submits a pre-filled
  manifest (name, homepage, webhook URL + generated secret, read-only Contents/
  Issues/PRs/Metadata, the webhook event set, and our redirect/setup URLs) to
  GitHub's org App-creation page.
- After the admin confirms on GitHub, GitHub redirects back with a temporary code;
  the backend **converts it** (`POST /app-manifests/{code}/conversions`) to obtain
  the **App ID, private key (PEM), and webhook secret automatically**, persists them
  encrypted as a `github_app` connection (pending installation), and sends the admin
  to GitHub to **install** the App.
- On the post-install redirect, the backend **captures the installation ID**,
  finalizes the connection (validates by minting an installation token), and returns
  the admin to the Connections page — ready to discover/sync.

The manual App-connect form stays as a fallback. No change to how webhooks/tokens
work once connected.

## Impact

- Affected specs: `github-connection` (manifest onboarding lifecycle), `rest-api`
  (manifest + setup callback endpoints), `web-ui` (create-App button + return handling).
- Affected code: new manifest-generation + `app-manifests/{code}/conversions` and
  installation-setup callbacks (github router); `GitHubConnection` gains a
  `pending_installation` state; `GitHubAppPort` gains manifest conversion; short-lived
  CSRF `state` storage; SvelteKit Connections page button + callback route.
- Security: admin-only initiation; CSRF `state` on the round-trip; exact redirect/
  setup URL matching; private key + webhook secret Fernet-encrypted at rest as today,
  never returned. The one-time manifest `code` and conversion are server-side.

## Non-goals

- Multi-org / multi-installation management UI (one App, installed per org, as today).
- Changing the PAT path or the webhook processing pipeline.
- Auto-selecting which repositories the installation covers (the admin chooses on
  GitHub's install screen).

<script lang="ts">
  import { getContext } from 'svelte';
  import type { AppContext } from '$lib/appContext';
  import { ConnectionsViewModel } from '$lib/viewmodels/ConnectionsViewModel.svelte';

  const ctx = getContext<AppContext>('app');
  const vm = new ConnectionsViewModel(ctx.githubApi, ctx.repositoriesApi, ctx.apiKeysApi);

  import type { IndexingMode } from '$lib/models';

  let token = $state('');
  let appId = $state('');
  let installationId = $state('');
  let privateKey = $state('');
  let webhookSecret = $state('');
  let orgMode = $state<IndexingMode>('project_intelligence');

  let keyLabel = $state('');
  let keyExpiry = $state('90'); // days; '' = never
  let copied = $state(false);
  // Typed-confirmation guard for the destructive connection delete.
  let confirmingId = $state<string | null>(null);
  let confirmText = $state('');

  async function confirmDelete(id: string) {
    await vm.remove(id);
    confirmingId = null;
    confirmText = '';
  }

  import { page } from '$app/state';
  const appConnected = $derived(page.url.searchParams.get('app_connected') === '1');
  const appError = $derived(page.url.searchParams.get('app_error'));

  // Fetch the manifest, then hand the browser off to GitHub via a POST form.
  async function createApp(org: string) {
    const boot = await vm.fetchAppManifest(org);
    if (!boot) return;
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = boot.post_url;
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'manifest';
    input.value = JSON.stringify(boot.manifest);
    form.appendChild(input);
    document.body.appendChild(form);
    form.submit();
  }

  $effect(() => {
    void vm.load();
    void vm.loadDeliveries();
    void vm.loadSyncActivity();
    void vm.loadOrganizations();
    void vm.loadApiKeys();
  });

  async function submitKey(event: SubmitEvent) {
    event.preventDefault();
    const days = keyExpiry === '' ? null : Number(keyExpiry);
    if (await vm.createApiKey(keyLabel, days)) keyLabel = '';
  }

  async function copyKey(value: string) {
    await navigator.clipboard.writeText(value);
    copied = true;
    setTimeout(() => (copied = false), 1500);
  }

  function keyState(k: { revoked: boolean; expires_at: string | null }): string {
    if (k.revoked) return 'revoked';
    if (k.expires_at && new Date(k.expires_at) < new Date()) return 'expired';
    return 'active';
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (await vm.connect(token)) token = '';
  }

  async function submitApp(event: SubmitEvent) {
    event.preventDefault();
    if (await vm.connectApp(appId, installationId, privateKey, webhookSecret)) {
      appId = installationId = privateKey = webhookSecret = '';
    }
  }
</script>

<h1>GitHub Connection</h1>
{#if appConnected}
  <p class="banner ok">✓ GitHub App connected. Run discovery to index its repositories.</p>
{/if}
{#if appError}
  <p class="banner err">GitHub App setup failed: {appError}</p>
{/if}
<p class="muted">
  Connect GitHub with one of two credential options. Both are read-only, encrypted at rest, and
  admin only. The credential's <strong>hourly rate limit</strong> governs how many repositories the
  nightly sync can cover — check it with <em>Test connection</em> below.
</p>

<h2>Fine-grained PAT</h2>
<p class="muted small">
  A read-only fine-grained token (Contents, Issues, Pull requests, Metadata). A <strong>personal</strong>
  token is ~5,000 requests/hour; an <strong>organization</strong> fine-grained PAT gets a higher org
  quota — prefer an org PAT when syncing many repos.
</p>
<form class="card" onsubmit={submit}>
  <label for="token">Fine-grained PAT</label>
  <div class="row">
    <input
      id="token"
      type="password"
      bind:value={token}
      placeholder="github_pat_…"
      minlength="8"
      required
    />
    <button disabled={vm.busy || token.length < 8}>Connect</button>
  </div>
  {#if vm.error}<p class="error">{vm.error}</p>{/if}
</form>

<h2>GitHub App (recommended)</h2>
<p class="muted small">
  A GitHub App installation gives short-lived scoped tokens, a higher installation rate limit, and
  near-real-time <strong>webhook</strong> updates — the best option for large orgs. Easiest path:
  use <strong>Create App</strong> next to an organization below (one-click — Mnemosyne pre-fills
  permissions/webhook and captures the credentials automatically). Or register an existing App
  manually here:
</p>
<form class="card" onsubmit={submitApp}>
  <div class="row">
    <input bind:value={appId} placeholder="App ID" required />
    <input bind:value={installationId} placeholder="Installation ID" required />
  </div>
  <textarea
    bind:value={privateKey}
    placeholder="-----BEGIN PRIVATE KEY-----&#10;…App private key PEM…"
    rows="4"
  ></textarea>
  <div class="row">
    <input type="password" bind:value={webhookSecret} placeholder="Webhook secret" required />
    <button disabled={vm.busy || appId.length < 1 || privateKey.length < 40}>
      Connect App
    </button>
  </div>
</form>

<h2>API keys</h2>
<p class="muted small">
  Generate a Mnemosyne API key to authenticate the <strong>MCP server</strong> or REST API from a
  Claude / OpenAI agent — paste it as the <code>Authorization: Bearer</code> credential in your
  connection. Keys grant read/query access (not admin), are shown <strong>once</strong>, and can be
  revoked anytime.
</p>
<form class="card" onsubmit={submitKey}>
  <div class="row">
    <input
      bind:value={keyLabel}
      placeholder="Label (e.g. claude-desktop)"
      minlength="1"
      maxlength="200"
      required
    />
    <select bind:value={keyExpiry} class="bulk-mode" aria-label="Expiry">
      <option value="7">Expires in 7 days</option>
      <option value="30">Expires in 30 days</option>
      <option value="90">Expires in 90 days</option>
      <option value="365">Expires in 365 days</option>
      <option value="">Never expires</option>
    </select>
    <button disabled={vm.keyBusy || keyLabel.trim().length < 1}>Generate key</button>
  </div>
  {#if vm.error}<p class="error">{vm.error}</p>{/if}
</form>

{#if vm.newKey}
  <div class="card key-reveal">
    <div class="eyebrow">New key — copy it now, it won't be shown again</div>
    <div class="row">
      <code class="key-value">{vm.newKey.key}</code>
      <button class="secondary" onclick={() => vm.newKey && copyKey(vm.newKey.key)}>
        {copied ? '✓ copied' : 'Copy'}
      </button>
      <button class="secondary" onclick={() => vm.dismissNewKey()}>Dismiss</button>
    </div>
  </div>
{/if}

{#if vm.apiKeys.length}
  <div class="card">
    <table>
      <thead>
        <tr><th>Label</th><th>Prefix</th><th>Expires</th><th>State</th><th></th></tr>
      </thead>
      <tbody>
        {#each vm.apiKeys as k (k.id)}
          {@const state = keyState(k)}
          <tr>
            <td><strong>{k.label}</strong></td>
            <td class="mono small">{k.prefix}…</td>
            <td class="muted small">
              {k.expires_at ? new Date(k.expires_at).toLocaleDateString() : 'never'}
            </td>
            <td>
              <span class="badge {state === 'active' ? 'ok' : 'err'}">{state}</span>
            </td>
            <td class="key-actions">
              {#if !k.revoked}
                <button class="secondary org-idx" onclick={() => vm.revokeApiKey(k.id)}>
                  Revoke
                </button>
              {/if}
              <button class="secondary org-idx danger" onclick={() => vm.deleteApiKey(k.id)}>
                Delete
              </button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

{#if vm.deliveries.length}
  <h2>Webhook activity</h2>
  <div class="card">
    <div class="scroll-y">
    <table>
      <thead><tr><th>Event</th><th>Repository</th><th>Outcome</th><th>When</th></tr></thead>
      <tbody>
        {#each vm.deliveries as d, i (i)}
          <tr>
            <td>{d.event}{#if d.action}<span class="muted"> · {d.action}</span>{/if}</td>
            <td>{d.repository_full_name ?? '—'}</td>
            <td><span class="badge {d.outcome === 'processed' ? 'ok' : ''}">{d.outcome}</span></td>
            <td class="muted">{new Date(d.received_at).toLocaleString()}</td>
          </tr>
        {/each}
      </tbody>
    </table>
    </div>
  </div>
{/if}

{#if vm.organizations.length}
  <h2>Organizations</h2>
  <p class="muted small">
    Choose which organizations Mnemosyne <strong>syncs</strong> (nightly), and index / un-index all
    of an organization's repositories at once. Un-indexed repos are removed from all intelligence
    (portfolio, scorecard, and per-repo metrics over REST + MCP). <strong>Sync now</strong> triggers
    an immediate sync of an org's indexed repos (otherwise they sync nightly at 03:00 UTC).
  </p>
  {#if vm.orgMessage}<p class="banner ok">{vm.orgMessage}</p>{/if}
  <div class="row org-controls">
    <span class="muted small">Index-all mode:</span>
    <select bind:value={orgMode} class="bulk-mode">
      <option value="docs_only">docs_only</option>
      <option value="project_intelligence">project_intelligence</option>
      <option value="code_metadata">code_metadata</option>
      <option value="code_context">code_context</option>
      <option value="full_context">full_context</option>
    </select>
  </div>
  <div class="card">
    <table>
      <thead>
        <tr><th>Organization</th><th>Indexed / total</th><th>Sync</th><th>Index</th></tr>
      </thead>
      <tbody>
        {#each vm.organizations as org (org.login)}
          <tr>
            <td><strong>{org.login}</strong></td>
            <td class="mono num">{org.enabled_repos} / {org.total_repos}</td>
            <td>
              <button
                class="secondary org-toggle"
                class:on={org.sync_enabled}
                onclick={() => vm.toggleOrganization(org.login, !org.sync_enabled)}
              >
                {org.sync_enabled ? '✓ syncing' : 'disabled'}
              </button>
            </td>
            <td>
              <button
                class="secondary org-idx"
                disabled={vm.orgBusy === org.login}
                onclick={() => vm.indexOrganization(org.login, true, orgMode)}
              >
                Index all
              </button>
              <button
                class="secondary org-idx"
                disabled={vm.orgBusy === org.login}
                onclick={() => vm.indexOrganization(org.login, false)}
              >
                Un-index all
              </button>
              <button
                class="secondary org-idx"
                disabled={vm.orgBusy === org.login || org.enabled_repos === 0}
                title={org.enabled_repos === 0 ? 'No indexed repos to sync' : 'Sync all indexed repos now'}
                onclick={() => vm.syncOrganization(org.login)}
              >
                Sync now
              </button>
              <button class="secondary org-idx" onclick={() => createApp(org.login)}>
                Create App
              </button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<h2>Sync activity</h2>
<p class="muted small">
  The nightly job (03:00 UTC) discovers, auto-enables new non-archived repos, then syncs all
  enabled ones. Recent runs and per-repo outcomes below.
</p>

{#if vm.syncRuns.length}
  <div class="card">
    <div class="eyebrow pad">Scheduled runs</div>
    <div class="scroll-y">
    <table>
      <thead>
        <tr><th>When</th><th>Discovered</th><th>Enabled</th><th>Enqueued</th><th>Skipped</th><th>Failed</th></tr>
      </thead>
      <tbody>
        {#each vm.syncRuns as r, i (i)}
          <tr>
            <td class="muted">{new Date(r.finished_at).toLocaleString()}</td>
            <td class="num">{r.discovered}</td>
            <td class="num">{r.newly_enabled}</td>
            <td class="num">{r.enqueued}</td>
            <td class="num">{r.skipped}</td>
            <td class="num">{#if r.failed}<span class="badge err">{r.failed}</span>{:else}0{/if}</td>
          </tr>
        {/each}
      </tbody>
    </table>
    </div>
  </div>
{:else}
  <p class="muted small">No scheduled runs recorded yet — the first fires at 03:00 UTC.</p>
{/if}

{#if vm.syncJobs.length}
  <div class="card">
    <div class="eyebrow pad">Recent sync jobs</div>
    <div class="scroll-y">
    <table>
      <thead><tr><th>Repository</th><th>Status</th><th>Trigger</th><th>When</th><th>Detail</th></tr></thead>
      <tbody>
        {#each vm.syncJobs as j (j.id)}
          <tr>
            <td>{j.repository_full_name ?? '—'}</td>
            <td>
              <span
                class="badge {j.status === 'succeeded'
                  ? 'ok'
                  : j.status === 'failed'
                    ? 'err'
                    : j.status === 'degraded'
                      ? 'warn'
                      : ''}"
              >
                {j.status}
              </span>
            </td>
            <td class="mono small">{j.triggered_by ?? '—'}</td>
            <td class="muted">{j.started_at ? new Date(j.started_at).toLocaleString() : '—'}</td>
            <td class="mono small err-text">{j.errors.length ? j.errors[0] : ''}</td>
          </tr>
        {/each}
      </tbody>
    </table>
    </div>
  </div>
{/if}

{#each vm.connections as connection (connection.id)}
  <div class="card connection">
    <div class="row">
      <strong>{connection.owner}</strong>
      <span class="badge">{connection.owner_type}</span>
      <span class="badge {connection.kind === 'github_app' ? 'ok' : ''}">
        {connection.kind === 'github_app' ? 'GitHub App' : 'PAT'}
      </span>
      <span class="badge {connection.status === 'active' ? 'ok' : 'err'}">{connection.status}</span>
      <span class="muted">…{connection.token_hint}</span>
    </div>
    <p class="muted">permissions: {connection.permissions.join(', ')}</p>
    {#if vm.testResults[connection.id]}
      {@const test = vm.testResults[connection.id]}
      <p class={test.ok ? '' : 'error'}>
        test: {test.ok ? 'ok' : 'failed'}
        {#if test.rate_limit}
          — rate limit <strong>{test.rate_limit.remaining.toLocaleString()}</strong> /
          {test.rate_limit.limit.toLocaleString()} per hour
          {#if test.rate_limit.limit <= 5000}
            <span class="badge warn">low — consider an org PAT or GitHub App</span>
          {/if}
        {/if}
      </p>
    {/if}
    <div class="row">
      <button class="secondary" onclick={() => vm.test(connection.id)}>Test connection</button>
      <button class="secondary" disabled={vm.busy} onclick={() => vm.discover(connection.id)}>
        Discover repositories
      </button>
      {#if connection.status !== 'deleting'}
        <button
          class="secondary danger"
          onclick={() => {
            confirmingId = connection.id;
            confirmText = '';
          }}
        >
          Delete
        </button>
      {:else}
        <span class="badge warn">deleting…</span>
      {/if}
    </div>
    {#if confirmingId === connection.id}
      <div class="confirm">
        <p class="error">
          This permanently deletes <strong>{connection.repository_count}</strong>
          {connection.repository_count === 1 ? 'repository' : 'repositories'} and all their
          indexed data (docs, issues, PRs, code). This cannot be undone.
        </p>
        <p class="muted">
          Type <strong>{connection.owner}</strong> to confirm.
        </p>
        <div class="row">
          <input placeholder={connection.owner} bind:value={confirmText} />
          <button
            class="secondary danger"
            disabled={confirmText !== connection.owner}
            onclick={() => confirmDelete(connection.id)}
          >
            Delete {connection.repository_count} repos
          </button>
          <button
            class="secondary"
            onclick={() => {
              confirmingId = null;
              confirmText = '';
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    {/if}
  </div>
{/each}
{#if vm.error}<p class="error">{vm.error}</p>{/if}

{#if vm.discovered}
  <div class="card">
    <h3>Discovered {vm.discovered.length} repositories</h3>
    <p class="muted">
      Enable the ones to index on the <a href="/">Repositories</a> dashboard.
    </p>
  </div>
{/if}

<style>
  .row {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
  }
  .card {
    margin-bottom: 1rem;
  }
  form input {
    flex: 1;
  }
  .small {
    font-size: 0.78rem;
  }
  .pad {
    padding: 0.2rem 0 0.6rem;
  }
  .err-text {
    color: var(--red);
    max-width: 320px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .org-toggle {
    font-family: 'IBM Plex Mono', ui-monospace, monospace;
    font-size: 0.72rem;
    padding: 0.25rem 0.6rem;
  }
  .org-toggle.on {
    color: var(--green);
    border-color: var(--green);
  }
  .org-controls {
    margin-bottom: 0.6rem;
  }
  .bulk-mode {
    font-size: 0.78rem;
    padding: 0.3rem 0.5rem;
  }
  .org-idx {
    font-size: 0.72rem;
    padding: 0.25rem 0.55rem;
    margin-right: 0.3rem;
  }
  .key-reveal {
    border-color: var(--accent);
  }
  .key-value {
    flex: 1;
    font-family: 'IBM Plex Mono', ui-monospace, monospace;
    font-size: 0.82rem;
    word-break: break-all;
    padding: 0.4rem 0.55rem;
    background: var(--surface-2, rgba(127, 127, 127, 0.1));
    border-radius: 4px;
  }
  .key-actions {
    display: flex;
    gap: 0.3rem;
    justify-content: flex-end;
  }
  .org-idx.danger,
  .danger {
    color: var(--red);
    border-color: var(--red);
  }
  .confirm {
    margin-top: 0.6rem;
    padding: 0.6rem 0.8rem;
    border: 1px solid var(--red);
    border-radius: 6px;
  }
  .confirm input {
    flex: 1;
    min-width: 160px;
  }
  .banner {
    padding: 0.5rem 0.8rem;
    border-radius: 6px;
    font-size: 0.85rem;
    margin: 0.4rem 0 0.8rem;
  }
  .banner.ok {
    color: var(--green);
    border: 1px solid var(--green);
  }
  .banner.err {
    color: var(--red);
    border: 1px solid var(--red);
  }
</style>

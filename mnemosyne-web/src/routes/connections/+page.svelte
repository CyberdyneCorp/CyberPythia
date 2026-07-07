<script lang="ts">
  import { getContext } from 'svelte';
  import type { AppContext } from '$lib/appContext';
  import { ConnectionsViewModel } from '$lib/viewmodels/ConnectionsViewModel.svelte';

  const ctx = getContext<AppContext>('app');
  const vm = new ConnectionsViewModel(ctx.githubApi, ctx.repositoriesApi);

  let token = $state('');
  let appId = $state('');
  let installationId = $state('');
  let privateKey = $state('');
  let webhookSecret = $state('');

  $effect(() => {
    void vm.load();
    void vm.loadDeliveries();
  });

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
<p class="muted">
  Register a read-only fine-grained personal access token (Contents, Issues, Pull requests,
  Metadata). The token is encrypted at rest and never shown again. Admin only.
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
<p class="muted">
  Register a GitHub App installation for short-lived scoped tokens and near-real-time
  webhook updates. Point the App webhook at <code>/api/v1/webhooks/github</code>.
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

{#if vm.deliveries.length}
  <h2>Webhook activity</h2>
  <div class="card">
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
{/if}

{#each vm.connections as connection (connection.id)}
  <div class="card connection">
    <div class="row">
      <strong>{connection.owner}</strong>
      <span class="badge">{connection.owner_type}</span>
      <span class="badge {connection.status === 'active' ? 'ok' : 'err'}">{connection.status}</span>
      <span class="muted">…{connection.token_hint}</span>
    </div>
    <p class="muted">permissions: {connection.permissions.join(', ')}</p>
    {#if vm.testResults[connection.id]}
      {@const test = vm.testResults[connection.id]}
      <p class={test.ok ? '' : 'error'}>
        test: {test.ok ? 'ok' : 'failed'}
        {#if test.rate_limit}
          — rate limit {test.rate_limit.remaining}/{test.rate_limit.limit}{/if}
      </p>
    {/if}
    <div class="row">
      <button class="secondary" onclick={() => vm.test(connection.id)}>Test connection</button>
      <button class="secondary" disabled={vm.busy} onclick={() => vm.discover(connection.id)}>
        Discover repositories
      </button>
      <button class="secondary" onclick={() => vm.remove(connection.id)}>Delete</button>
    </div>
  </div>
{/each}

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
</style>

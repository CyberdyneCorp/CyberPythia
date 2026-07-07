<script lang="ts">
  import { getContext } from 'svelte';
  import type { AppContext } from '$lib/appContext';
  import { ConnectionsViewModel } from '$lib/viewmodels/ConnectionsViewModel.svelte';

  const ctx = getContext<AppContext>('app');
  const vm = new ConnectionsViewModel(ctx.githubApi, ctx.repositoriesApi);

  let token = $state('');

  $effect(() => {
    void vm.load();
  });

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (await vm.connect(token)) token = '';
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

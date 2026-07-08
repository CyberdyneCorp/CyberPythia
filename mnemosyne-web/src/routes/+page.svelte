<script lang="ts">
  import { getContext } from 'svelte';
  import type { AppContext } from '$lib/appContext';
  import RepositoryCard from '$lib/components/RepositoryCard.svelte';
  import { RepositoryListViewModel } from '$lib/viewmodels/RepositoryListViewModel.svelte';

  const ctx = getContext<AppContext>('app');
  const vm = new RepositoryListViewModel(ctx.repositoriesApi);

  $effect(() => {
    void vm.load();
  });
</script>

<div class="page-head">
  <h1>Repositories</h1>
  {#if vm.repositories.length}
    <span class="mono count">
      {vm.filtered.length}
      {#if vm.filtered.length !== vm.repositories.length}of {vm.repositories.length}{/if}
    </span>
  {/if}
</div>
<div class="filters">
  <input class="filter" placeholder="Filter repositories… (name, language, mode)" bind:value={vm.filter} />
  {#if vm.organizations.length > 1}
    <select bind:value={vm.organizationFilter} class="org-select">
      <option value="">All organizations</option>
      {#each vm.organizations as org (org)}
        <option value={org}>{org}</option>
      {/each}
    </select>
  {/if}
</div>
{#if vm.error}<p class="error">{vm.error}</p>{/if}
{#if vm.loading && vm.repositories.length === 0}
  <p class="muted">Loading…</p>
{:else if vm.repositories.length === 0}
  <div class="card">
    <p>
      No repositories discovered yet. An administrator can register a GitHub credential and run
      discovery on the <a href="/connections">GitHub Connection</a> page.
    </p>
  </div>
{:else}
  <div class="grid">
    {#each vm.filtered as repo (repo.id)}
      <RepositoryCard
        {repo}
        syncState={vm.syncStateFor(repo.id)}
        onToggle={(enabled) => vm.setSelection(repo, enabled)}
        onMode={(mode) => vm.setSelection(repo, true, mode)}
        onSync={() => vm.triggerSync(repo)}
      />
    {/each}
  </div>
{/if}

<style>
  .page-head {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
  }
  .count {
    font-size: 0.75rem;
    color: var(--tx3);
  }
  .filters {
    display: flex;
    gap: 0.6rem;
    margin: 0.9rem 0 1rem;
    flex-wrap: wrap;
  }
  .filter {
    flex: 1;
    min-width: 240px;
    max-width: 460px;
  }
  .org-select {
    min-width: 180px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 1rem;
  }
</style>

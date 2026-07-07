<script lang="ts">
  import type { IndexingMode, Repository } from '$lib/models';

  let {
    repo,
    syncState,
    onToggle,
    onMode,
    onSync
  }: {
    repo: Repository;
    syncState: string | null;
    onToggle: (enabled: boolean) => void;
    onMode: (mode: IndexingMode) => void;
    onSync: () => void;
  } = $props();
</script>

<div class="card repo">
  <div class="head">
    <a href={repo.enabled ? `/repos/${repo.id}` : undefined} class="name">{repo.full_name}</a>
    {#if repo.primary_language}<span class="badge">{repo.primary_language}</span>{/if}
    {#if repo.archived}<span class="badge warn">archived</span>{/if}
    {#if syncState === 'running' || syncState === 'pending'}
      <span class="badge warn">sync {syncState}…</span>
    {:else if syncState === 'failed'}
      <span class="badge err">sync failed</span>
    {:else if repo.last_synced_at}
      <span class="badge ok">synced {new Date(repo.last_synced_at).toLocaleString()}</span>
    {:else}
      <span class="badge">never synced</span>
    {/if}
  </div>
  <p class="muted desc">{repo.description ?? 'No description.'}</p>
  <div class="controls">
    <label>
      <input
        type="checkbox"
        checked={repo.enabled}
        onchange={(e) => onToggle(e.currentTarget.checked)}
      />
      indexed
    </label>
    <select
      value={repo.indexing_mode}
      disabled={!repo.enabled}
      onchange={(e) => onMode(e.currentTarget.value as IndexingMode)}
    >
      <option value="docs_only">docs_only</option>
      <option value="project_intelligence">project_intelligence</option>
      <option value="code_metadata">code_metadata</option>
    </select>
    <button
      class="secondary"
      disabled={!repo.enabled || syncState === 'running' || syncState === 'pending'}
      onclick={onSync}
    >
      Sync now
    </button>
  </div>
</div>

<style>
  .repo {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .name {
    font-weight: 600;
  }
  .desc {
    margin: 0;
    font-size: 0.88rem;
  }
  .controls {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    font-size: 0.85rem;
  }
</style>

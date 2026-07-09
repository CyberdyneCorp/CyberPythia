<script lang="ts">
  import { getContext } from 'svelte';
  import type { AppContext } from '$lib/appContext';
  import { SearchViewModel } from '$lib/viewmodels/SearchViewModel.svelte';

  const ctx = getContext<AppContext>('app');
  const vm = new SearchViewModel(ctx.intelligenceApi, ctx.repositoriesApi);

  const KINDS = ['docs', 'code', 'issues', 'repositories'] as const;

  $effect(() => {
    void vm.loadOrganizations();
  });

  function submit(event: SubmitEvent) {
    event.preventDefault();
    void vm.run();
  }
</script>

<h1>Search</h1>
<p class="muted lede">
  Search across every indexed repository at once — documentation, code, or issues (semantic /
  keyword), or fuzzy-find a repository by name. Scope to one organization if you like.
</p>

<form class="bar" onsubmit={submit}>
  <input
    class="q"
    bind:value={vm.query}
    placeholder="Search all repositories…"
    minlength="2"
    required
  />
  <select bind:value={vm.kind} aria-label="What to search">
    {#each KINDS as k (k)}<option value={k}>{k}</option>{/each}
  </select>
  {#if vm.kind !== 'repositories' && vm.organizations.length}
    <select bind:value={vm.organization} aria-label="Organization">
      <option value="">All orgs</option>
      {#each vm.organizations as o (o)}<option value={o}>{o}</option>{/each}
    </select>
  {/if}
  <button disabled={vm.busy || vm.query.trim().length < 2}>{vm.busy ? '…' : 'Search'}</button>
</form>

{#if vm.error}<p class="error">{vm.error}</p>{/if}

{#if vm.kind === 'repositories'}
  {#if vm.repos.length}
    <div class="results">
      {#each vm.repos as r (r.repository_id)}
        <a class="row" href={`/repos/${r.repository_id}`}>
          <span class="name">{r.full_name}</span>
          <span class="muted small">{r.primary_language ?? ''}</span>
          <span class="muted desc">{r.description ?? ''}</span>
        </a>
      {/each}
    </div>
  {:else if vm.searched && !vm.busy}
    <p class="muted">No repositories match.</p>
  {/if}
{:else if vm.kind === 'code' && vm.results.length}
  <div class="results">
    {#each vm.results as r, i (i)}
      <div class="code-hit">
        <a class="code-loc" href={`/repos/${r.repository_id}?tab=files`}>
          <span class="name">{r.full_name}</span>
          <span class="mono path">{r.path}{r.start_line ? `:${r.start_line}` : ''}</span>
          {#if r.symbol}<span class="mono sym">{r.symbol}</span>{/if}
          <span class="mono score">{r.score.toFixed(2)}</span>
        </a>
        {#if r.excerpt}<pre class="snippet">{r.excerpt}</pre>{/if}
      </div>
    {/each}
  </div>
{:else if vm.results.length}
  <div class="results">
    {#each vm.results as r, i (i)}
      <a class="row" href={`/repos/${r.repository_id}`}>
        <span class="name">{r.full_name}</span>
        {#if r.number !== undefined}
          <span class="mono small">#{r.number}</span>
        {/if}
        <span class="title">{r.title ?? r.path ?? r.symbol ?? ''}</span>
        {#if r.excerpt}<span class="muted excerpt">{r.excerpt}</span>{/if}
        <span class="mono score">{r.score.toFixed(2)}</span>
      </a>
    {/each}
  </div>
{:else if vm.searched && !vm.busy}
  <p class="muted">No matches. (Code search needs repos indexed in a code mode.)</p>
{/if}

<style>
  .lede {
    font-size: 0.85rem;
    margin: 0.4rem 0 1.2rem;
    max-width: 640px;
  }
  .bar {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: 1.2rem;
  }
  .bar .q {
    flex: 1;
    min-width: 220px;
  }
  .results {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--bd, rgba(127, 127, 127, 0.2));
    border-radius: 6px;
    overflow: hidden;
  }
  .row {
    display: grid;
    grid-template-columns: minmax(140px, 1fr) auto minmax(120px, 1.5fr) auto;
    gap: 0.6rem;
    align-items: baseline;
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid var(--bd, rgba(127, 127, 127, 0.12));
    text-decoration: none;
    color: inherit;
  }
  .row:hover {
    background: var(--panel2, rgba(127, 127, 127, 0.06));
  }
  .name {
    font-weight: 600;
  }
  .title {
    color: var(--tx2, inherit);
  }
  .excerpt,
  .desc {
    grid-column: 1 / -1;
    font-size: 0.78rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .small {
    font-size: 0.75rem;
  }
  .score {
    color: var(--tx3);
    font-size: 0.75rem;
  }
  .code-hit {
    border-bottom: 1px solid var(--bd, rgba(127, 127, 127, 0.12));
    padding: 0.5rem 0.8rem;
  }
  .code-loc {
    display: flex;
    gap: 0.6rem;
    align-items: baseline;
    text-decoration: none;
    color: inherit;
    flex-wrap: wrap;
  }
  .code-loc .path {
    color: var(--accent, #e8a33d);
    font-size: 0.78rem;
  }
  .code-loc .sym {
    font-size: 0.75rem;
    color: var(--tx2);
  }
  .snippet {
    margin: 0.4rem 0 0;
    padding: 0.5rem 0.7rem;
    background: var(--panel2, rgba(127, 127, 127, 0.08));
    border-radius: 5px;
    font-size: 0.76rem;
    overflow-x: auto;
    white-space: pre-wrap;
  }
</style>

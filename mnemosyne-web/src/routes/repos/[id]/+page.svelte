<script lang="ts">
  import { getContext } from 'svelte';
  import { page } from '$app/state';
  import type { AppContext } from '$lib/appContext';
  import DocumentViewer from '$lib/components/DocumentViewer.svelte';
  import ContextPackPanel from '$lib/components/ContextPackPanel.svelte';
  import {
    RepositoryDetailViewModel,
    type Tab
  } from '$lib/viewmodels/RepositoryDetailViewModel.svelte';
  import { AskViewModel } from '$lib/viewmodels/AskViewModel.svelte';

  const ctx = getContext<AppContext>('app');
  const repoId = page.params.id!;
  const vm = new RepositoryDetailViewModel(ctx.repositoriesApi, repoId);
  const askVm = new AskViewModel(ctx.contextApi, repoId);

  const TABS: { id: Tab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'documentation', label: 'Documentation' },
    { id: 'openspec', label: 'OpenSpec' },
    { id: 'issues', label: 'Issues' },
    { id: 'pull-requests', label: 'Pull Requests' },
    { id: 'files', label: 'Files' },
    { id: 'metrics', label: 'Metrics' },
    { id: 'agent-context', label: 'Agent Context' }
  ];

  $effect(() => {
    const requested = page.url.searchParams.get('tab') as Tab | null;
    void vm.open(requested ?? 'overview');
  });

  function fmtDuration(seconds: unknown): string {
    if (typeof seconds !== 'number') return '—';
    if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
    if (seconds < 172800) return `${(seconds / 3600).toFixed(1)} h`;
    return `${(seconds / 86400).toFixed(1)} d`;
  }
</script>

<h1>{vm.summary?.repository.full_name ?? 'Repository'}</h1>

<div class="tabs">
  {#each TABS as tab (tab.id)}
    <button class:active={vm.tab === tab.id} class="secondary" onclick={() => vm.open(tab.id)}>
      {tab.label}
    </button>
  {/each}
</div>

{#if vm.error}<p class="error">{vm.error}</p>{/if}
{#if vm.loading}<p class="muted">Loading…</p>{/if}

{#if vm.tab === 'overview' && vm.summary}
  {@const repo = vm.summary.repository}
  {@const s = vm.summary.summary}
  <div class="card">
    <p>{repo.description ?? 'No description.'}</p>
    <p class="muted">
      {repo.primary_language ?? 'unknown language'} · branch {repo.default_branch} · mode
      {repo.indexing_mode} · last sync
      {repo.last_synced_at ? new Date(repo.last_synced_at).toLocaleString() : 'never'}
    </p>
    {#if s}
      <div class="stats">
        <div class="card stat"><strong>{s.documents ?? 0}</strong><span>docs</span></div>
        <div class="card stat">
          <strong>{s.openspec_changes ?? 0}</strong><span>openspec changes</span>
        </div>
        <div class="card stat">
          <strong>{s.open_issues ?? 0}/{s.closed_issues ?? 0}</strong><span>issues open/closed</span>
        </div>
        <div class="card stat">
          <strong>{s.open_prs ?? 0}/{s.merged_prs ?? 0}</strong><span>PRs open/merged</span>
        </div>
        <div class="card stat">
          <strong>{fmtDuration(s.avg_issue_resolution_seconds)}</strong>
          <span>avg issue resolution</span>
        </div>
        <div class="card stat">
          <strong>{fmtDuration(s.avg_pr_merge_seconds)}</strong><span>avg PR merge</span>
        </div>
      </div>
    {/if}
  </div>
{/if}

{#if vm.tab === 'documentation'}
  <table>
    <thead><tr><th>Path</th><th>Type</th><th>Title</th></tr></thead>
    <tbody>
      {#each vm.docs as doc, i (i)}
        <tr>
          <td><button class="link" onclick={() => vm.openDoc(doc.id)}>{doc.path}</button></td>
          <td><span class="badge">{doc.type}</span></td>
          <td>{doc.title}{#if doc.quarantined} <span class="badge err">quarantined</span>{/if}</td>
        </tr>
      {/each}
    </tbody>
  </table>
  {#if vm.selectedDoc}
    <DocumentViewer doc={vm.selectedDoc} onClose={() => vm.closeDoc()} />
  {/if}
{/if}

{#if vm.tab === 'openspec'}
  {#each vm.openspec as change, i (i)}
    <details class="card">
      <summary>
        <strong>{change.change_id}</strong>
        <span class="badge {change.status === 'active' ? 'warn' : 'ok'}">{change.status}</span>
        {#if change.affected_specs.length}
          <span class="muted">specs: {change.affected_specs.join(', ')}</span>
        {/if}
      </summary>
      {#if change.proposal}<h4>Proposal</h4><pre>{change.proposal}</pre>{/if}
      {#if change.tasks}<h4>Tasks</h4><pre>{change.tasks}</pre>{/if}
      {#if change.design}<h4>Design</h4><pre>{change.design}</pre>{/if}
    </details>
  {:else}
    <p class="muted">No OpenSpec content captured.</p>
  {/each}
{/if}

{#if vm.tab === 'issues'}
  <table>
    <thead>
      <tr><th>#</th><th>Title</th><th>State</th><th>Author</th><th>Labels</th><th>Resolution</th></tr>
    </thead>
    <tbody>
      {#each vm.issues as issue, i (i)}
        <tr>
          <td>{issue.number}</td>
          <td>{issue.title}</td>
          <td><span class="badge {issue.state === 'open' ? 'warn' : 'ok'}">{issue.state}</span></td>
          <td>{issue.author}</td>
          <td>{issue.labels.join(', ')}</td>
          <td>{fmtDuration(issue.resolution_time_seconds)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}

{#if vm.tab === 'pull-requests'}
  <table>
    <thead>
      <tr><th>#</th><th>Title</th><th>State</th><th>Author</th><th>Δ</th><th>To merge</th><th>To review</th></tr>
    </thead>
    <tbody>
      {#each vm.pullRequests as pr, i (i)}
        <tr>
          <td>{pr.number}</td>
          <td>{pr.title}</td>
          <td><span class="badge {pr.merged ? 'ok' : 'warn'}">{pr.state}</span></td>
          <td>{pr.author}</td>
          <td>+{pr.additions}/−{pr.deletions}</td>
          <td>{fmtDuration(pr.time_to_merge_seconds)}</td>
          <td>{fmtDuration(pr.time_to_first_review_seconds)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}

{#if vm.tab === 'files'}
  <table>
    <thead><tr><th>Path</th><th>Language</th><th>Size</th><th>Kind</th></tr></thead>
    <tbody>
      {#each vm.files as file, i (i)}
        <tr>
          <td><code>{file.path}</code></td>
          <td>{file.language ?? ''}</td>
          <td>{file.size_bytes}</td>
          <td>{#if file.important_kind}<span class="badge">{file.important_kind}</span>{/if}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}

{#if vm.tab === 'metrics' && vm.metrics}
  {@const im = vm.metrics.issue_metrics}
  {@const pm = vm.metrics.pr_metrics}
  <p class="muted">Computed at {new Date(vm.metrics.computed_at).toLocaleString()}</p>
  <div class="stats">
    <div class="card stat">
      <strong>{fmtDuration(im.avg_resolution_seconds)}</strong><span>avg issue resolution</span>
    </div>
    <div class="card stat">
      <strong>{fmtDuration(im.median_resolution_seconds)}</strong><span>median issue resolution</span>
    </div>
    <div class="card stat">
      <strong>{fmtDuration(pm.avg_time_to_merge_seconds)}</strong><span>avg PR merge</span>
    </div>
    <div class="card stat">
      <strong>{fmtDuration(pm.avg_time_to_first_review_seconds)}</strong><span>avg first review</span>
    </div>
    <div class="card stat">
      <strong
        >{typeof pm.merge_rate === 'number' ? `${Math.round(pm.merge_rate * 100)}%` : '—'}</strong
      ><span>merge rate</span>
    </div>
    <div class="card stat">
      <strong>{(im.stale_issues as unknown[])?.length ?? 0}</strong><span>stale issues</span>
    </div>
    <div class="card stat">
      <strong>{(pm.stale_prs as unknown[])?.length ?? 0}</strong><span>stale PRs</span>
    </div>
  </div>
{/if}

{#if vm.tab === 'agent-context'}
  <div class="card">
    <div class="ask-row">
      <select bind:value={askVm.mode}>
        <option value="ask">Ask a question</option>
        <option value="context-pack">Build context pack</option>
      </select>
      <input
        placeholder="e.g. How is authentication implemented in this repository?"
        bind:value={askVm.question}
        onkeydown={(e) => e.key === 'Enter' && askVm.submit()}
      />
      <button disabled={askVm.busy} onclick={() => askVm.submit()}>
        {askVm.busy ? 'Working…' : 'Go'}
      </button>
    </div>
    {#if askVm.error}<p class="error">{askVm.error}</p>{/if}
  </div>

  {#if askVm.askResult}
    <div class="card">
      <p>{askVm.askResult.answer}</p>
      {#if askVm.askResult.sources.length}
        <h4>Sources</h4>
        <ul>
          {#each askVm.askResult.sources as source, i (i)}
            <li>
              <a href={`/repos/${repoId}?tab=documentation`}>{source.path}</a>
              <span class="muted">score {source.score}</span>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  {/if}

  {#if askVm.contextPack}
    <ContextPackPanel pack={askVm.contextPack} {repoId} />
  {/if}
{/if}

<style>
  .tabs {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
  }
  .tabs button.active {
    border-color: var(--accent);
    color: var(--accent);
  }
  .stats {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
    gap: 0.75rem;
    margin-top: 1rem;
  }
  .stat {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .stat strong {
    font-size: 1.3rem;
  }
  .stat span {
    color: var(--muted);
    font-size: 0.8rem;
  }
  button.link {
    background: none;
    border: none;
    color: var(--accent);
    padding: 0;
    cursor: pointer;
  }
  .ask-row {
    display: flex;
    gap: 0.75rem;
  }
  .ask-row input {
    flex: 1;
  }
  details.card {
    margin-bottom: 0.75rem;
  }
  pre {
    background: var(--surface-2);
    padding: 0.75rem;
    border-radius: 8px;
    overflow-x: auto;
    white-space: pre-wrap;
  }
</style>

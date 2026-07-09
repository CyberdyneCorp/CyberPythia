<script lang="ts">
  import { getContext } from 'svelte';
  import { page } from '$app/state';
  import type { AppContext } from '$lib/appContext';
  import DocumentViewer from '$lib/components/DocumentViewer.svelte';
  import ContextPackPanel from '$lib/components/ContextPackPanel.svelte';
  import HealthPanel from '$lib/components/HealthPanel.svelte';
  import DeliveryPanel from '$lib/components/DeliveryPanel.svelte';
  import {
    RepositoryDetailViewModel,
    type Tab
  } from '$lib/viewmodels/RepositoryDetailViewModel.svelte';
  import { AskViewModel } from '$lib/viewmodels/AskViewModel.svelte';
  import { CodeSearchViewModel } from '$lib/viewmodels/CodeSearchViewModel.svelte';

  const ctx = getContext<AppContext>('app');
  const repoId = page.params.id!;
  const vm = new RepositoryDetailViewModel(ctx.repositoriesApi, repoId);
  const askVm = new AskViewModel(ctx.contextApi, repoId);
  const codeVm = new CodeSearchViewModel(ctx.codeApi, repoId);

  const TABS: { id: Tab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'capabilities', label: 'Capabilities' },
    { id: 'documentation', label: 'Documentation' },
    { id: 'openspec', label: 'OpenSpec' },
    { id: 'issues', label: 'Issues' },
    { id: 'pull-requests', label: 'Pull Requests' },
    { id: 'files', label: 'Files' },
    { id: 'metrics', label: 'Metrics' },
    { id: 'code-context', label: 'Code Context' },
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
    <button class="tab" class:active={vm.tab === tab.id} onclick={() => vm.open(tab.id)}>
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
  <HealthPanel api={ctx.intelligenceApi} {repoId} />
  <DeliveryPanel api={ctx.intelligenceApi} {repoId} />
{/if}

{#if vm.tab === 'capabilities' && vm.capabilities}
  {@const cap = vm.capabilities}
  <div class="card">
    <p>{cap.description ?? 'No description.'}</p>
    <div class="stats">
      <div class="card stat"><strong>{cap.issues.bugs}</strong><span>open bugs</span></div>
      <div class="card stat">
        <strong>{cap.issues.open}/{cap.issues.closed}</strong><span>issues open/closed</span>
      </div>
      <div class="card stat">
        <strong>{cap.pull_requests.open}/{cap.pull_requests.merged}</strong><span>PRs open/merged</span>
      </div>
      <div class="card stat"><strong>{cap.documents}</strong><span>docs</span></div>
    </div>
    <h3>Capabilities</h3>
    {#if cap.capabilities.length}
      <div class="chips">
        {#each cap.capabilities as c (c)}<span class="chip">{c}</span>{/each}
      </div>
    {:else}
      <p class="muted small">No OpenSpec capabilities indexed — see documentation topics below.</p>
    {/if}
    {#if cap.documentation_topics.length}
      <h3>Documentation topics</h3>
      <ul class="topics">
        {#each cap.documentation_topics as t (t)}<li>{t}</li>{/each}
      </ul>
    {/if}
  </div>

  <div class="card">
    <div class="row">
      <h3>Feature document</h3>
      <button
        class="secondary"
        disabled={vm.featureDocBusy}
        onclick={() => vm.generateFeatureDoc()}
      >
        {vm.featureDocBusy ? 'Generating…' : 'Generate'}
      </button>
    </div>
    <p class="muted small">
      A grounded Markdown write-up of everything this project does, synthesized from indexed
      docs / OpenSpec / code.
    </p>
    {#if vm.featureDoc}
      {#if !vm.featureDoc.grounded}
        <p class="muted small">Limited context — the document may be incomplete.</p>
      {/if}
      <pre class="doc">{vm.featureDoc.document}</pre>
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

{#if vm.tab === 'code-context'}
  <div class="card">
    <div class="ask-row">
      <input
        placeholder="Search code semantically, e.g. how are GPU kernels dispatched"
        bind:value={codeVm.query}
        onkeydown={(e) => e.key === 'Enter' && codeVm.search()}
      />
      <button disabled={codeVm.busy} onclick={() => codeVm.search()}>
        {codeVm.busy ? 'Searching…' : 'Search'}
      </button>
    </div>
    {#if codeVm.notIndexed}
      <p class="muted">
        Source code is not indexed for this repository. Enable the
        <code>code_context</code> or <code>full_context</code> indexing mode on the
        dashboard and re-sync to search code.
      </p>
    {/if}
    {#if codeVm.error}<p class="error">{codeVm.error}</p>{/if}
  </div>

  {#each codeVm.results as match, i (i)}
    <div class="card code-match">
      <div class="head">
        <code>{match.path}</code>
        {#if match.symbol_name}
          <span class="badge">{match.chunk_type} {match.symbol_name}</span>
        {:else}
          <span class="badge">{match.chunk_type}</span>
        {/if}
        <span class="muted">lines {match.start_line}–{match.end_line} · score {match.score}</span>
      </div>
      <pre>{match.excerpt}</pre>
    </div>
  {/each}
{/if}

{#if vm.tab === 'agent-context'}
  <div class="ask-row">
    <select bind:value={askVm.mode}>
      <option value="ask">Ask a question</option>
      <option value="context-pack">Build context pack</option>
    </select>
    <input
      placeholder={askVm.mode === 'ask'
        ? 'Ask anything about this repository…'
        : 'Describe the task… e.g. “add rate limiting to the webhook receiver”'}
      bind:value={askVm.question}
      onkeydown={(e) => e.key === 'Enter' && askVm.submit()}
    />
    <button disabled={askVm.busy} onclick={() => askVm.submit()}>
      {askVm.mode === 'ask' ? 'Ask' : 'Build pack'}
    </button>
  </div>
  {#if askVm.error}<p class="error">{askVm.error}</p>{/if}

  {#if askVm.busy}
    <div class="thinking mono">
      <span class="pulse">▮▮▮</span>
      {askVm.mode === 'ask' ? 'retrieving grounded context…' : 'assembling context pack…'}
    </div>
  {/if}

  {#if askVm.askResult && !askVm.busy}
    <div class="answer card">
      {#if askVm.askResult.grounded === false}
        <div class="eyebrow ungrounded">Not grounded — no supporting context found</div>
      {/if}
      <p class="answer-body">{askVm.askResult.answer}</p>
      {#if askVm.askResult.sources.length}
        <div class="sources">
          <div class="eyebrow">Sources</div>
          {#each askVm.askResult.sources as source, i (i)}
            <a class="src" href={`/repos/${repoId}?tab=documentation`}>
              <span class="src-n mono">[{i + 1}]</span>
              <span class="src-ref mono">{source.path}</span>
              {#if source.title}<span class="src-kind">{source.title}</span>{/if}
              <span class="src-score mono">{source.score}</span>
            </a>
          {/each}
        </div>
      {/if}
    </div>
  {/if}

  {#if askVm.contextPack && !askVm.busy}
    <ContextPackPanel pack={askVm.contextPack} {repoId} />
  {/if}
{/if}

<style>
  .tabs {
    display: flex;
    gap: 0.25rem;
    flex-wrap: wrap;
    margin: 0.4rem 0 1.2rem;
    border-bottom: 1px solid var(--line);
  }
  .tab {
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 0.55rem 0.75rem;
    margin-bottom: -1px;
    font-size: 0.82rem;
    font-weight: 500;
    color: var(--tx3);
    white-space: nowrap;
  }
  .tab:hover {
    color: var(--tx);
    opacity: 1;
  }
  .tab.active {
    color: var(--tx);
    border-bottom-color: var(--ac);
    font-weight: 600;
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
    gap: 0.6rem;
    margin-bottom: 0.4rem;
  }
  .ask-row input {
    flex: 1;
  }
  .thinking {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    color: var(--tx3);
    font-size: 0.78rem;
    margin: 1rem 0;
  }
  .pulse {
    animation: pulse 1s ease infinite;
  }
  @keyframes pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.3;
    }
  }
  .answer {
    margin-top: 0.9rem;
  }
  .ungrounded {
    color: var(--ac);
    margin-bottom: 0.6rem;
  }
  .answer-body {
    font-size: 0.85rem;
    line-height: 1.7;
    color: var(--tx2);
    margin: 0;
    white-space: pre-wrap;
  }
  .sources {
    margin-top: 0.9rem;
    border-top: 1px solid var(--line);
    padding-top: 0.8rem;
  }
  .sources .eyebrow {
    margin-bottom: 0.5rem;
  }
  .src {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    padding: 0.2rem 0;
    color: var(--tx);
  }
  .src:hover {
    color: var(--tx);
  }
  .src-n {
    color: var(--ac);
    font-size: 0.68rem;
    width: 22px;
  }
  .src-ref {
    font-size: 0.75rem;
    color: var(--tx2);
  }
  .src-kind {
    font-size: 0.72rem;
    color: var(--tx3);
    flex: 1;
  }
  .src-score {
    font-size: 0.68rem;
    color: var(--tx3);
    font-variant-numeric: tabular-nums;
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
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0.3rem 0 0.6rem;
  }
  .chip {
    font-family: 'IBM Plex Mono', ui-monospace, monospace;
    font-size: 0.75rem;
    padding: 0.2rem 0.5rem;
    border: 1px solid var(--accent, #e8a33d);
    border-radius: 999px;
  }
  .topics {
    margin: 0.3rem 0 0.4rem 1.1rem;
    font-size: 0.85rem;
  }
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .doc {
    margin-top: 0.6rem;
    padding: 0.8rem;
    background: var(--panel2, rgba(127, 127, 127, 0.08));
    border-radius: 6px;
    font-family: 'IBM Plex Mono', ui-monospace, monospace;
    font-size: 0.8rem;
    white-space: pre-wrap;
    max-height: 500px;
    overflow-y: auto;
  }
</style>

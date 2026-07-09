<script lang="ts">
  import { getContext } from 'svelte';
  import type { AppContext } from '$lib/appContext';
  import { IntelligenceViewModel } from '$lib/viewmodels/IntelligenceViewModel.svelte';
  import { DeliveryViewModel } from '$lib/viewmodels/DeliveryViewModel.svelte';
  import type { DeliveryScorecardEntry, PortfolioEntry } from '$lib/models';

  const ctx = getContext<AppContext>('app');
  const vm = new IntelligenceViewModel(ctx.intelligenceApi);
  const deliveryVm = new DeliveryViewModel(ctx.intelligenceApi);

  const CAP = 25;
  let boardFilter = $state('');
  let boardAll = $state(false);
  let cardFilter = $state('');
  let cardAll = $state(false);
  let org = $state(''); // '' = all organizations

  $effect(() => {
    void vm.loadPortfolio();
    void deliveryVm.loadScorecard();
  });

  function owner(fullName: string): string {
    return fullName.split('/')[0];
  }

  // Organizations present in the indexed intelligence data (the synced ones).
  const organizations = $derived(
    Array.from(
      new Set([
        ...(vm.overview?.leaderboard ?? []).map((e) => owner(e.full_name)),
        ...deliveryVm.scorecard.map((e) => owner(e.full_name))
      ])
    ).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()))
  );

  function byOrg<T extends { full_name: string }>(list: T[]): T[] {
    return org ? list.filter((e) => owner(e.full_name) === org) : list;
  }

  function gradeColor(grade: string | null): string {
    if (grade === 'A' || grade === 'B') return 'var(--green)';
    if (grade === 'C') return 'var(--ac)';
    if (grade === 'D' || grade === 'F') return 'var(--red)';
    return 'var(--tx3)';
  }
  function gradeBg(grade: string | null): string {
    if (grade === 'A' || grade === 'B') return 'var(--greenb)';
    if (grade === 'C') return 'var(--acb)';
    if (grade === 'D' || grade === 'F') return 'var(--redb)';
    return 'var(--panel2)';
  }

  function matches<T extends { full_name: string }>(list: T[], q: string, all: boolean): T[] {
    const f = q.trim().toLowerCase();
    const hit = f ? list.filter((e) => e.full_name.toLowerCase().includes(f)) : list;
    return f || all ? hit : hit.slice(0, CAP);
  }

  const board = $derived(
    vm.overview ? matches(byOrg(vm.overview.leaderboard), boardFilter, boardAll) : []
  );
  const cards = $derived(matches(byOrg(deliveryVm.scorecard), cardFilter, cardAll));

  function arrow(d: string | null): string {
    if (d === 'down') return '↓ improving';
    if (d === 'up') return '↑ growing';
    if (d === 'flat') return '→ flat';
    return '—';
  }
  function scoreW(e: PortfolioEntry): string {
    return e.overall !== null ? `${e.overall}%` : '0%';
  }
</script>

<div class="page-head">
  <h1>Engineering Intelligence</h1>
  {#if vm.overview}
    <span class="mono sub">{vm.overview.scored} of {vm.overview.total_repositories} scored</span>
  {/if}
  {#if organizations.length > 1}
    <select class="org-select" bind:value={org} aria-label="Filter by organization">
      <option value="">All organizations</option>
      {#each organizations as o (o)}<option value={o}>{o}</option>{/each}
    </select>
  {/if}
</div>
<p class="muted lede">
  Portfolio health and delivery across indexed repositories. Scores come from the latest sync;
  repositories not yet synced show as insufficient data.
</p>

{#if vm.error}<p class="error">{vm.error}</p>{/if}
{#if vm.busy && !vm.overview}<p class="muted">Loading…</p>{/if}

{#if vm.overview}
  {@const o = vm.overview}

  <!-- Health leaderboard -->
  <section class="panel">
    <div class="panel-head">
      <h2 class="title">Health leaderboard</h2>
      <span class="mono eyebrow-inline">score 0–100 · grade A–F</span>
      <input class="mini-filter" placeholder="Filter…" bind:value={boardFilter} />
    </div>
    {#each board as entry, i (entry.repository_id)}
      <a class="lrow" href={`/repos/${entry.repository_id}`}>
        <span class="mono rank">{boardFilter ? '' : i + 1}</span>
        <span class="name">{entry.full_name}</span>
        {#if entry.has_data}
          <span class="bar"><span class="fill" style="width:{scoreW(entry)};background:{gradeColor(entry.grade)}"></span></span>
          <span class="mono score">{entry.overall}</span>
          <span class="mono gradechip" style="color:{gradeColor(entry.grade)};background:{gradeBg(entry.grade)}">{entry.grade}</span>
        {:else}
          <span class="insufficient">insufficient data</span>
        {/if}
      </a>
    {/each}
    {#if !boardFilter && byOrg(o.leaderboard).length > CAP}
      <button class="showall secondary" onclick={() => (boardAll = !boardAll)}>
        {boardAll ? 'Show top 25' : `Show all ${byOrg(o.leaderboard).length}`}
      </button>
    {/if}
  </section>

  <!-- Groupings -->
  <div class="grid3">
    <div class="panel">
      <div class="panel-head"><span class="ico ok-c">▲</span><span class="title">Most active</span></div>
      {#if o.most_active.length}
        {#each o.most_active as name, i (i)}<div class="grow">{name}</div>{/each}
      {:else}<div class="grow muted">—</div>{/if}
    </div>
    <div class="panel">
      <div class="panel-head"><span class="ico muted">◴</span><span class="title">Abandoned</span></div>
      {#if o.abandoned.length}
        {#each o.abandoned as name, i (i)}<div class="grow">{name}</div>{/each}
      {:else}<div class="grow muted">None</div>{/if}
    </div>
    <div class="panel">
      <div class="panel-head"><span class="ico err-c">●</span><span class="title">Bug-heavy</span></div>
      {#if o.bug_heavy.length}
        {#each o.bug_heavy as name, i (i)}<div class="grow">{name}</div>{/each}
      {:else}<div class="grow muted">—</div>{/if}
    </div>
  </div>
{/if}

<!-- Delivery scorecard -->
<section class="panel">
  <div class="panel-head">
    <h2 class="title">Delivery scorecard</h2>
    <span class="mono eyebrow-inline">PM/PO signals · trends fill as history accrues</span>
    <input class="mini-filter" placeholder="Filter…" bind:value={cardFilter} />
  </div>
  {#if deliveryVm.error}<p class="error pad">{deliveryVm.error}</p>{/if}
  {#if cards.length}
    <div class="scroll">
      <table>
        <thead>
          <tr><th>Repository</th><th>Median cycle</th><th>Throughput</th><th>Backlog</th><th>At-risk</th></tr>
        </thead>
        <tbody>
          {#each cards as e (e.repository_id)}
            <tr>
              <td><a href={`/repos/${e.repository_id}`}>{e.full_name}</a></td>
              <td class="num">{e.has_data && e.median_cycle_days !== null ? `${e.median_cycle_days} d` : '—'}</td>
              <td class="mono">{arrow(e.throughput_direction)}</td>
              <td>
                {#if e.backlog_shrinking === null}<span class="muted mono small">collecting</span>
                {:else if e.backlog_shrinking}<span class="badge ok">shrinking</span>
                {:else}<span class="badge">not shrinking</span>{/if}
              </td>
              <td class="num">{e.at_risk_milestones > 0 ? `⚠ ${e.at_risk_milestones}` : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if !cardFilter && byOrg(deliveryVm.scorecard).length > CAP}
      <button class="showall secondary" onclick={() => (cardAll = !cardAll)}>
        {cardAll ? 'Show top 25' : `Show all ${byOrg(deliveryVm.scorecard).length}`}
      </button>
    {/if}
  {:else if !deliveryVm.busy}
    <p class="muted pad">No delivery data yet.</p>
  {/if}
</section>

<style>
  .page-head {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
  }
  .sub {
    font-size: 0.75rem;
    color: var(--tx3);
  }
  .org-select {
    margin-left: auto;
    font-size: 0.8rem;
    padding: 0.3rem 0.5rem;
  }
  .lede {
    font-size: 0.85rem;
    margin: 0.4rem 0 1.3rem;
    max-width: 640px;
  }
  .panel {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    box-shadow: var(--sh);
    overflow: hidden;
    margin-bottom: 1.1rem;
  }
  .panel-head {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.8rem 1.1rem;
    border-bottom: 1px solid var(--line);
  }
  .panel-head .title {
    font-size: 0.83rem;
    font-weight: 600;
    color: var(--tx2);
  }
  .eyebrow-inline {
    font-size: 0.66rem;
    color: var(--tx3);
    letter-spacing: 0.04em;
  }
  .mini-filter {
    margin-left: auto;
    padding: 0.3rem 0.6rem;
    font-size: 0.78rem;
    width: 150px;
  }
  .lrow {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.55rem 1.1rem;
    border-bottom: 1px solid var(--line);
    color: var(--tx);
  }
  .lrow:hover {
    background: var(--panel2);
    color: var(--tx);
  }
  .rank {
    width: 20px;
    font-size: 0.66rem;
    color: var(--tx3);
  }
  .lrow .name {
    flex: 1;
    font-size: 0.8rem;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .bar {
    width: 90px;
    height: 5px;
    border-radius: 3px;
    background: var(--line);
    overflow: hidden;
    flex: none;
  }
  .fill {
    display: block;
    height: 100%;
    border-radius: 3px;
  }
  .score {
    width: 26px;
    text-align: right;
    font-size: 0.72rem;
    color: var(--tx2);
    font-variant-numeric: tabular-nums;
  }
  .gradechip {
    width: 22px;
    text-align: center;
    padding: 0.12rem 0;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 600;
  }
  .insufficient {
    font-family: 'IBM Plex Mono', ui-monospace, monospace;
    font-size: 0.62rem;
    color: var(--tx3);
    border: 1px dashed var(--line2);
    border-radius: 4px;
    padding: 0.12rem 0.5rem;
  }
  .showall {
    margin: 0.6rem 1.1rem;
    font-size: 0.78rem;
  }
  .grid3 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 0.9rem;
    margin-bottom: 1.1rem;
  }
  .ico {
    font-size: 0.75rem;
  }
  .ok-c {
    color: var(--green);
  }
  .err-c {
    color: var(--red);
  }
  .grow {
    padding: 0.5rem 1rem;
    border-bottom: 1px solid var(--line);
    font-size: 0.8rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .scroll {
    max-height: 560px;
    overflow: auto;
  }
  .small {
    font-size: 0.7rem;
  }
  .pad {
    padding: 0.8rem 1.1rem;
  }
</style>

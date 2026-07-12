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

  // Everything is scoped server-side by the org filter: reloading portfolio,
  // scorecard, the org rollup, and the activity/stale panels whenever it changes.
  $effect(() => {
    const scope = org || undefined;
    void vm.loadPortfolio(scope);
    void deliveryVm.loadScorecard(scope);
    void vm.loadOrgDetail(org);
  });

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
    vm.overview ? matches(vm.overview.leaderboard, boardFilter, boardAll) : []
  );
  const cards = $derived(matches(deliveryVm.scorecard, cardFilter, cardAll));

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
  {#if vm.organizations.length > 1}
    <select class="org-select" bind:value={org} aria-label="Filter by organization">
      <option value="">All organizations</option>
      {#each vm.organizations as o (o)}<option value={o}>{o}</option>{/each}
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
    {#if !boardFilter && o.leaderboard.length > CAP}
      <button class="showall secondary" onclick={() => (boardAll = !boardAll)}>
        {boardAll ? 'Show top 25' : `Show all ${o.leaderboard.length}`}
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
    {#if !cardFilter && deliveryVm.scorecard.length > CAP}
      <button class="showall secondary" onclick={() => (cardAll = !cardAll)}>
        {cardAll ? 'Show top 25' : `Show all ${deliveryVm.scorecard.length}`}
      </button>
    {/if}
  {:else if !deliveryVm.busy}
    <p class="muted pad">No delivery data yet.</p>
  {/if}
</section>

<!-- Organization overview (server rollup, when an org is selected) -->
{#if vm.orgIntel}
  {@const oi = vm.orgIntel}
  <section class="panel">
    <div class="panel-head">
      <h2 class="title">{oi.organization} overview</h2>
      <span class="mono eyebrow-inline">server rollup</span>
    </div>
    <div class="orgstats">
      <div class="stat"><strong>{oi.scored}/{oi.total_repositories}</strong><span>scored</span></div>
      <div class="stat"><strong>{oi.average_health ?? '—'}</strong><span>avg health</span></div>
      <div class="stat"><strong>{oi.median_health ?? '—'}</strong><span>median</span></div>
      <div class="stat"><strong>{oi.at_risk_milestones}</strong><span>at-risk milestones</span></div>
      <div class="stat">
        <strong>
          {#each Object.entries(oi.grade_distribution) as [g, n] (g)}<span class="gchip">{g}:{n}</span>{/each}
          {#if !Object.keys(oi.grade_distribution).length}—{/if}
        </strong><span>grades</span>
      </div>
    </div>
  </section>
{/if}

<!-- Readiness (when an org is selected) -->
{#if vm.readiness}
  {@const rd = vm.readiness}
  <section class="panel">
    <div class="panel-head">
      <h2 class="title">Readiness</h2>
      <span class="mono eyebrow-inline">observable gate · MVP → READY → DONE</span>
    </div>
    <div class="orgstats">
      <div class="stat"><strong class="gate DONE">{rd.distribution.DONE}</strong><span>done</span></div>
      <div class="stat"><strong class="gate READY">{rd.distribution.READY}</strong><span>ready</span></div>
      <div class="stat"><strong class="gate MVP">{rd.distribution.MVP}</strong><span>mvp</span></div>
      <div class="stat"><strong>{rd.total}</strong><span>total</span></div>
    </div>
    {#each rd.repositories as r (r.repository_id)}
      <a class="rdrow" href={`/repos/${r.repository_id}`}>
        <span class="gatechip {r.gate}">{r.gate}</span>
        <span class="fn">{r.full_name}</span>
        {#if r.gate === 'MVP' && r.missing_for_ready.length}
          <span class="miss">for READY: {r.missing_for_ready.join(', ')}</span>
        {:else if r.gate === 'READY' && r.missing_for_done.length}
          <span class="miss">for DONE: {r.missing_for_done.join(', ')}</span>
        {/if}
      </a>
    {/each}
    {#if !rd.repositories.length}<p class="muted pad">No repositories.</p>{/if}
  </section>
{/if}

<!-- Readiness regressions (alerts) -->
{#if vm.regressions && vm.regressions.regressions.length}
  {@const rg = vm.regressions}
  <section class="panel">
    <div class="panel-head">
      <h2 class="title">Readiness regressions</h2>
      <span class="mono eyebrow-inline">gate dropped vs. previous snapshot</span>
    </div>
    {#each rg.regressions as r (r.repository_id)}
      <a class="frow" href={`/repos/${r.repository_id}`}>
        <span class="badge err">▼</span>
        <span class="fn">{r.full_name}</span>
        <span class="ft"><span class="mono">{r.from_gate} → {r.to_gate}</span></span>
        <span class="mono days">{r.date}</span>
      </a>
    {/each}
  </section>
{/if}

<!-- Vulnerabilities (when an org is selected) -->
{#if vm.vulnerabilities}
  {@const vn = vm.vulnerabilities}
  <section class="panel">
    <div class="panel-head">
      <h2 class="title">Vulnerabilities</h2>
      <span class="mono eyebrow-inline">open Dependabot alerts</span>
    </div>
    <div class="orgstats">
      <div class="stat"><strong style="color:var(--red)">{vn.total_critical}</strong><span>critical</span></div>
      <div class="stat"><strong style="color:var(--ac)">{vn.total_high}</strong><span>high</span></div>
      <div class="stat"><strong>{vn.repositories.length}</strong><span>affected repos</span></div>
    </div>
    {#each vn.repositories as r (r.repository_id)}
      <a class="frow" href={`/repos/${r.repository_id}`}>
        <span class="badge err">{r.critical}C</span>
        <span class="badge warn">{r.high}H</span>
        <span class="fn">{r.full_name}</span>
      </a>
    {/each}
    {#if !vn.repositories.length}
      <p class="muted pad">No open critical/high alerts captured (needs a sync with the App's Dependabot-alerts grant).</p>
    {/if}
  </section>
{/if}

<!-- Organization capabilities (when an org is selected) -->
{#if vm.capabilities}
  {@const cp = vm.capabilities}
  <section class="panel">
    <div class="panel-head">
      <h2 class="title">Capabilities</h2>
      <span class="mono eyebrow-inline">
        {cp.capabilities.length} across {cp.repositories} repos · {cp.total_open_bugs} open bugs
      </span>
    </div>
    {#if cp.capabilities.length}
      <div class="chips pad">
        {#each cp.capabilities as c (c)}<span class="chip">{c}</span>{/each}
      </div>
    {:else}<p class="muted pad">No OpenSpec capability areas indexed yet.</p>{/if}
  </section>
{/if}

<!-- OpenSpec coverage (when an org is selected) -->
{#if vm.openspec}
  {@const cov = vm.openspec}
  <section class="panel">
    <div class="panel-head">
      <h2 class="title">OpenSpec coverage</h2>
      <span class="mono eyebrow-inline">
        {Math.round(cov.coverage * 100)}% · {cov.with_openspec.length}/{cov.total} repos
      </span>
    </div>
    <div class="cov-bar"><span class="cov-fill" style="width:{cov.coverage * 100}%"></span></div>
    <div class="grid2">
      <div>
        <div class="eyebrow pad">Has OpenSpec ({cov.with_openspec.length})</div>
        {#each cov.with_openspec as r (r.repository_id)}
          <a class="covrow" href={`/repos/${r.repository_id}`}>
            <span class="fn">{r.full_name}</span>
            <span class="mono small">{r.openspec_changes} changes</span>
          </a>
        {/each}
      </div>
      <div>
        <div class="eyebrow pad">Missing — adoption targets ({cov.without_openspec.length})</div>
        {#each cov.without_openspec as r (r.repository_id)}
          <a class="covrow" href={`/repos/${r.repository_id}`}>
            <span class="fn">{r.full_name}</span>
            <span class="mono small">{r.last_synced_at ? '' : 'not synced'}</span>
          </a>
        {/each}
        {#if !cov.without_openspec.length}<p class="muted small pad">All covered 🎉</p>{/if}
      </div>
    </div>
  </section>
{/if}

<!-- Recent activity + Needs attention (scoped by the org filter) -->
<div class="grid2">
  <section class="panel">
    <div class="panel-head"><h2 class="title">Recent activity</h2></div>
    {#if vm.activity && (vm.activity.recent_issues.length || vm.activity.recent_pull_requests.length)}
      {#each vm.activity.recent_pull_requests.slice(0, 6) as p (p.repository_id + 'pr' + p.number)}
        <a class="frow" href={`/repos/${p.repository_id}`}>
          <span class="badge {p.merged ? 'ok' : ''}">PR</span>
          <span class="fn">{p.full_name} #{p.number}</span>
          <span class="ft">{p.title}</span>
        </a>
      {/each}
      {#each vm.activity.recent_issues.slice(0, 6) as it (it.repository_id + 'is' + it.number)}
        <a class="frow" href={`/repos/${it.repository_id}`}>
          <span class="badge">issue</span>
          <span class="fn">{it.full_name} #{it.number}</span>
          <span class="ft">{it.title}</span>
        </a>
      {/each}
    {:else}<p class="muted pad">No recent activity.</p>{/if}
  </section>

  <section class="panel">
    <div class="panel-head">
      <h2 class="title">Needs attention</h2>
      <span class="mono eyebrow-inline">stale &gt; 30d</span>
    </div>
    {#if vm.staleIssues.length || vm.stalePrs.length}
      {#each vm.stalePrs.slice(0, 5) as p (p.repository_id + 'pr' + p.number)}
        <a class="frow" href={`/repos/${p.repository_id}`}>
          <span class="badge err">PR</span>
          <span class="fn">{p.full_name} #{p.number}</span>
          <span class="ft">{p.title}</span>
          <span class="mono days">{p.stale_days}d</span>
        </a>
      {/each}
      {#each vm.staleIssues.slice(0, 5) as it (it.repository_id + 'is' + it.number)}
        <a class="frow" href={`/repos/${it.repository_id}`}>
          <span class="badge err">issue</span>
          <span class="fn">{it.full_name} #{it.number}</span>
          <span class="ft">{it.title}</span>
          <span class="mono days">{it.stale_days}d</span>
        </a>
      {/each}
    {:else}<p class="muted pad">Nothing stale. 🎉</p>{/if}
  </section>
</div>

<style>
  .grid2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }
  @media (max-width: 720px) {
    .grid2 {
      grid-template-columns: 1fr;
    }
  }
  .orgstats {
    display: flex;
    flex-wrap: wrap;
    gap: 1.4rem;
    padding: 0.4rem 0.2rem 0.2rem;
  }
  .stat {
    display: flex;
    flex-direction: column;
  }
  .stat strong {
    font-size: 1.1rem;
  }
  .stat span {
    font-size: 0.72rem;
    color: var(--tx3);
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }
  .chip {
    font-size: 0.72rem;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    background: var(--panel2);
    border: 1px solid var(--line);
    white-space: nowrap;
  }
  .gchip {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.9rem;
    margin-right: 0.4rem;
  }
  .gate.DONE {
    color: var(--green);
  }
  .gate.READY {
    color: var(--ac);
  }
  .gate.MVP {
    color: var(--tx3);
  }
  .rdrow {
    display: grid;
    grid-template-columns: auto minmax(140px, 1fr) 3fr;
    gap: 0.6rem;
    align-items: baseline;
    padding: 0.35rem 1.1rem;
    border-bottom: 1px solid var(--line);
    text-decoration: none;
    color: inherit;
  }
  .rdrow:hover {
    background: var(--panel2);
  }
  .gatechip {
    font-family: 'IBM Plex Mono', ui-monospace, monospace;
    font-size: 0.62rem;
    font-weight: 600;
    text-align: center;
    padding: 0.12rem 0.5rem;
    border-radius: 4px;
    width: 58px;
  }
  .gatechip.DONE {
    color: var(--green);
    background: var(--greenb);
  }
  .gatechip.READY {
    color: var(--ac);
    background: var(--acb);
  }
  .gatechip.MVP {
    color: var(--tx3);
    background: var(--panel2);
  }
  .miss {
    font-size: 0.7rem;
    color: var(--tx3);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .frow {
    display: grid;
    grid-template-columns: auto minmax(120px, 1fr) 2fr auto;
    gap: 0.5rem;
    align-items: baseline;
    padding: 0.35rem 0.2rem;
    border-bottom: 1px solid var(--bd, rgba(127, 127, 127, 0.12));
    text-decoration: none;
    color: inherit;
  }
  .frow:hover {
    background: var(--panel2, rgba(127, 127, 127, 0.06));
  }
  .fn {
    font-size: 0.78rem;
    color: var(--tx2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .ft {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .days {
    font-size: 0.72rem;
    color: var(--tx3);
  }
  .cov-bar {
    height: 8px;
    border-radius: 999px;
    background: var(--panel2, rgba(127, 127, 127, 0.15));
    overflow: hidden;
    margin: 0.3rem 0 0.8rem;
  }
  .cov-fill {
    display: block;
    height: 100%;
    background: var(--green);
  }
  .covrow {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.3rem 0.2rem;
    border-bottom: 1px solid var(--bd, rgba(127, 127, 127, 0.1));
    text-decoration: none;
    color: inherit;
  }
  .covrow:hover {
    background: var(--panel2, rgba(127, 127, 127, 0.06));
  }
  .covrow .fn {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
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

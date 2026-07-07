<script lang="ts">
  import type { IntelligenceApi } from '$lib/api/mnemosyneApi';
  import { RepositoryDeliveryViewModel } from '$lib/viewmodels/DeliveryViewModel.svelte';

  let { api, repoId }: { api: IntelligenceApi; repoId: string } = $props();
  const vm = new RepositoryDeliveryViewModel(api, repoId);

  $effect(() => {
    void vm.load();
  });

  function days(seconds: number | null): string {
    return seconds === null ? '—' : `${(seconds / 86400).toFixed(1)} d`;
  }
</script>

<div class="card">
  <h3>Delivery</h3>
  {#if vm.error}<p class="error">{vm.error}</p>{/if}
  {#if vm.busy && !vm.flow}<p class="muted">Loading…</p>{/if}

  {#if vm.flow && !vm.flow.has_data}
    <p class="muted">Insufficient data — no issues or PRs captured yet.</p>
  {/if}

  {#if vm.flow?.has_data}
    {@const f = vm.flow}
    <h4>Cycle time (issue resolution)</h4>
    <div class="stats">
      <div class="stat"><span>p50</span><strong>{days(f.resolution_seconds.p50)}</strong></div>
      <div class="stat"><span>p85</span><strong>{days(f.resolution_seconds.p85)}</strong></div>
      <div class="stat"><span>p95</span><strong>{days(f.resolution_seconds.p95)}</strong></div>
      <div class="stat"><span>WIP issues</span><strong>{f.wip_issues}</strong></div>
      <div class="stat"><span>untriaged</span><strong>{f.untriaged_issues}</strong></div>
    </div>

    <h4>Aging open issues</h4>
    <div class="aging">
      {#each Object.entries(f.issue_aging) as [bucket, count] (bucket)}
        <div class="bucket"><span>{bucket}d</span><strong>{count}</strong></div>
      {/each}
    </div>
  {/if}

  {#if vm.workMix?.has_data}
    <h4>Work mix</h4>
    <div class="aging">
      {#each Object.entries(vm.workMix.distribution) as [cls, count] (cls)}
        <div class="bucket"><span>{cls.replace('_', ' ')}</span><strong>{count}</strong></div>
      {/each}
    </div>
  {/if}

  {#if vm.forecast}
    <h4>Backlog forecast</h4>
    {#if vm.forecast.projected_clear_date}
      <p>Projected to clear by <strong>{vm.forecast.projected_clear_date}</strong></p>
    {:else}
      <p class="muted">{vm.forecast.reason ?? 'collecting history'}</p>
    {/if}
  {/if}

  {#if vm.milestones.length}
    <h4>Milestones</h4>
    <table>
      <thead><tr><th>Milestone</th><th>Progress</th><th>Due</th><th>Projected</th></tr></thead>
      <tbody>
        {#each vm.milestones as m (m.number)}
          <tr>
            <td>{m.title}</td>
            <td>{m.percent_complete !== null ? `${m.percent_complete}%` : '—'}</td>
            <td>{m.due_on ?? '—'}</td>
            <td>
              {#if m.at_risk}<span class="badge err">⚠ {m.projected_completion}</span>
              {:else}{m.projected_completion ?? '—'}{/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .stats,
  .aging {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin: 0.5rem 0 1rem;
  }
  .stat,
  .bucket {
    display: flex;
    flex-direction: column;
    padding: 0.4rem 0.7rem;
    border: 1px solid var(--border, #ddd);
    border-radius: 6px;
    min-width: 70px;
  }
  .stat span,
  .bucket span {
    font-size: 0.8rem;
    opacity: 0.7;
  }
  h4 {
    margin: 0.75rem 0 0.25rem;
  }
</style>

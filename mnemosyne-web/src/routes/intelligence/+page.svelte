<script lang="ts">
  import { getContext } from 'svelte';
  import type { AppContext } from '$lib/appContext';
  import { IntelligenceViewModel } from '$lib/viewmodels/IntelligenceViewModel.svelte';

  const ctx = getContext<AppContext>('app');
  const vm = new IntelligenceViewModel(ctx.intelligenceApi);

  $effect(() => {
    void vm.loadPortfolio();
  });

  function gradeClass(grade: string | null): string {
    if (!grade) return '';
    return grade === 'A' || grade === 'B' ? 'ok' : grade === 'F' ? 'err' : '';
  }
</script>

<h1>Engineering Intelligence</h1>
<p class="muted">
  Portfolio health across indexed repositories. Scores are computed from the latest sync —
  repositories not yet synced show as insufficient data.
</p>

{#if vm.error}<p class="error">{vm.error}</p>{/if}
{#if vm.busy && !vm.overview}<p class="muted">Loading…</p>{/if}

{#if vm.overview}
  {@const o = vm.overview}
  <p class="muted">{o.scored} of {o.total_repositories} repositories scored</p>

  <h2>Health leaderboard</h2>
  <div class="card">
    <table>
      <thead><tr><th>Repository</th><th>Grade</th><th>Score</th></tr></thead>
      <tbody>
        {#each o.leaderboard as entry (entry.repository_id)}
          <tr>
            <td><a href={`/repos/${entry.repository_id}`}>{entry.full_name}</a></td>
            <td>
              {#if entry.has_data}
                <span class="badge {gradeClass(entry.grade)}">{entry.grade}</span>
              {:else}
                <span class="muted">insufficient data</span>
              {/if}
            </td>
            <td>{entry.overall ?? '—'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  <div class="grid">
    <div class="card">
      <h3>Most active</h3>
      {#if o.most_active.length}
        <ul>{#each o.most_active as name, i (i)}<li>{name}</li>{/each}</ul>
      {:else}<p class="muted">—</p>{/if}
    </div>
    <div class="card">
      <h3>Abandoned</h3>
      {#if o.abandoned.length}
        <ul>{#each o.abandoned as name, i (i)}<li>{name}</li>{/each}</ul>
      {:else}<p class="muted">None</p>{/if}
    </div>
    <div class="card">
      <h3>Bug-heavy</h3>
      {#if o.bug_heavy.length}
        <ul>{#each o.bug_heavy as name, i (i)}<li>{name}</li>{/each}</ul>
      {:else}<p class="muted">—</p>{/if}
    </div>
  </div>
{/if}

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
  }
  .card {
    margin-bottom: 1rem;
  }
  ul {
    margin: 0;
    padding-left: 1.1rem;
  }
</style>

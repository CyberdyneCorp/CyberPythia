<script lang="ts">
  import type { IntelligenceApi } from '$lib/api/mnemosyneApi';
  import { RepositoryHealthViewModel } from '$lib/viewmodels/IntelligenceViewModel.svelte';

  let { api, repoId }: { api: IntelligenceApi; repoId: string } = $props();
  const vm = new RepositoryHealthViewModel(api, repoId);

  $effect(() => {
    void vm.load();
  });

  function gradeClass(grade: string | null): string {
    if (!grade) return '';
    return grade === 'A' || grade === 'B' ? 'ok' : grade === 'F' ? 'err' : '';
  }

  function fmtComponent(score: number | null): string {
    return score === null ? 'n/a' : String(Math.round(score));
  }
</script>

<div class="card">
  <div class="row">
    <h3>Health</h3>
    {#if vm.health?.has_data}
      <span class="badge {gradeClass(vm.health.grade)}">{vm.health.grade}</span>
      <strong>{vm.health.overall}</strong><span class="muted">/ 100</span>
    {/if}
  </div>

  {#if vm.error}<p class="error">{vm.error}</p>{/if}
  {#if vm.busy && !vm.health}<p class="muted">Scoring…</p>{/if}

  {#if vm.health && !vm.health.has_data}
    <p class="muted">Insufficient data — this repository has not been synced yet.</p>
  {/if}

  {#if vm.health?.has_data}
    <div class="components">
      {#each vm.health.components as c (c.name)}
        <div class="component" class:na={c.score === null}>
          <span>{c.name.replace('_', '/')}</span>
          <strong>{fmtComponent(c.score)}</strong>
        </div>
      {/each}
    </div>

    {#if vm.health.findings.length}
      <ul class="findings">
        {#each vm.health.findings as f, i (i)}
          <li class={f.severity}>{f.message}</li>
        {/each}
      </ul>
    {/if}
  {/if}
</div>

<style>
  .row {
    display: flex;
    gap: 0.5rem;
    align-items: baseline;
  }
  .components {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 0.5rem;
    margin: 0.75rem 0;
  }
  .component {
    display: flex;
    justify-content: space-between;
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border, #ddd);
    border-radius: 6px;
  }
  .component.na {
    opacity: 0.5;
  }
  .findings {
    margin: 0;
    padding-left: 1.1rem;
  }
  .findings li.warning {
    color: var(--ac);
  }
  .findings li.critical {
    color: var(--red);
  }
</style>

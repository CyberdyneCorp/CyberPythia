<script lang="ts">
  import type { IntelligenceApi } from '$lib/api/mnemosyneApi';
  import { RepositoryHealthViewModel } from '$lib/viewmodels/IntelligenceViewModel.svelte';

  let { api, repoId }: { api: IntelligenceApi; repoId: string } = $props();
  const vm = new RepositoryHealthViewModel(api, repoId);

  $effect(() => {
    void vm.load();
  });

  const CIRC = 220; // 2πr, r=35

  function gradeColor(grade: string | null): string {
    if (grade === 'A' || grade === 'B') return 'var(--green)';
    if (grade === 'C') return 'var(--ac)';
    if (grade === 'D' || grade === 'F') return 'var(--red)';
    return 'var(--tx3)';
  }
  function compColor(score: number | null): string {
    if (score === null) return 'var(--tx3)';
    if (score >= 75) return 'var(--green)';
    if (score >= 50) return 'var(--ac)';
    return 'var(--red)';
  }
  function fmt(score: number | null): string {
    return score === null ? 'n/a' : String(Math.round(score));
  }
</script>

<section class="panel">
  <div class="head">Health</div>
  {#if vm.error}<p class="error">{vm.error}</p>{/if}
  {#if vm.busy && !vm.health}<p class="muted">Scoring…</p>{/if}

  {#if vm.health && !vm.health.has_data}
    <p class="muted">Insufficient data — this repository has not been synced yet.</p>
  {/if}

  {#if vm.health?.has_data}
    {@const h = vm.health}
    <div class="body">
      <div class="ring">
        <svg width="84" height="84" viewBox="0 0 84 84">
          <circle cx="42" cy="42" r="35" fill="none" stroke="var(--line)" stroke-width="7" />
          <circle
            cx="42"
            cy="42"
            r="35"
            fill="none"
            stroke={gradeColor(h.grade)}
            stroke-width="7"
            stroke-linecap="round"
            stroke-dasharray="{((h.overall ?? 0) / 100) * CIRC} {CIRC}"
            transform="rotate(-90 42 42)"
          />
        </svg>
        <div class="ring-c">
          <div class="ring-score">{h.overall}</div>
          <div class="mono ring-grade" style="color:{gradeColor(h.grade)}">{h.grade}</div>
        </div>
      </div>
      <div class="comps">
        {#each h.components as c (c.name)}
          <div class="comp">
            <span class="ck">{c.name.replace('_', '/')}</span>
            <span class="cbar"><span class="cfill" style="width:{c.score ?? 0}%;background:{compColor(c.score)}"></span></span>
            <span class="mono cv" style="color:{compColor(c.score)}">{fmt(c.score)}</span>
          </div>
        {/each}
      </div>
    </div>

    {#if h.findings.length}
      <div class="findings">
        {#each h.findings as f, i (i)}
          <div class="finding">
            <span class="sev sev-{f.severity}">{f.severity}</span>
            <span class="fmsg">{f.message}</span>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</section>

<style>
  .panel {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    box-shadow: var(--sh);
    padding: 1.1rem 1.25rem;
    margin-bottom: 1rem;
  }
  .head {
    font-size: 0.83rem;
    font-weight: 600;
    color: var(--tx2);
    margin-bottom: 0.9rem;
  }
  .body {
    display: flex;
    gap: 1.4rem;
    align-items: center;
  }
  .ring {
    position: relative;
    width: 84px;
    height: 84px;
    flex: none;
  }
  .ring-c {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  .ring-score {
    font-size: 1.4rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }
  .ring-grade {
    font-size: 0.7rem;
    font-weight: 600;
  }
  .comps {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }
  .comp {
    display: flex;
    align-items: center;
    gap: 0.65rem;
  }
  .ck {
    width: 100px;
    font-size: 0.75rem;
    color: var(--tx2);
  }
  .cbar {
    flex: 1;
    height: 5px;
    border-radius: 3px;
    background: var(--line);
    overflow: hidden;
  }
  .cfill {
    display: block;
    height: 100%;
    border-radius: 3px;
  }
  .cv {
    width: 32px;
    text-align: right;
    font-size: 0.72rem;
    font-variant-numeric: tabular-nums;
  }
  .findings {
    margin-top: 1rem;
    border-top: 1px solid var(--line);
    padding-top: 0.8rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .finding {
    display: flex;
    gap: 0.65rem;
    align-items: baseline;
  }
  .sev {
    font-family: 'IBM Plex Mono', ui-monospace, monospace;
    font-size: 0.58rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    padding: 0.12rem 0.45rem;
    border-radius: 4px;
    text-transform: uppercase;
    flex: none;
  }
  .sev-info {
    color: var(--blue);
    background: var(--blueb);
  }
  .sev-warning {
    color: var(--ac);
    background: var(--acb);
  }
  .sev-critical {
    color: var(--red);
    background: var(--redb);
  }
  .fmsg {
    font-size: 0.78rem;
    color: var(--tx2);
  }
</style>

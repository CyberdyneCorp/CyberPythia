<script lang="ts">
  import type { ContextPack } from '$lib/models';

  let { pack, repoId }: { pack: ContextPack; repoId: string } = $props();
</script>

<div class="card">
  <h3>Context pack — “{pack.query}”</h3>
  <p class="muted">{pack.repository_summary}</p>

  {#if pack.risks.length}
    <h4>Risks</h4>
    <ul>
      {#each pack.risks as risk, i (i)}<li>{risk}</li>{/each}
    </ul>
  {/if}

  {#if pack.relevant_docs.length}
    <h4>Relevant docs</h4>
    <ul>
      {#each pack.relevant_docs as doc, i (i)}
        <li>
          <a href={`/repos/${repoId}?tab=documentation`}>{doc.path}</a>
          <span class="badge">{doc.doc_type}</span>
          <span class="muted">score {doc.score}</span>
        </li>
      {/each}
    </ul>
  {/if}

  {#if pack.relevant_openspec_changes.length}
    <h4>OpenSpec changes</h4>
    <ul>
      {#each pack.relevant_openspec_changes as change (change.change_id)}
        <li>
          <a href={`/repos/${repoId}?tab=openspec`}>{change.change_id}</a>
          <span class="badge">{change.status}</span>
        </li>
      {/each}
    </ul>
  {/if}

  {#if pack.relevant_issues.length}
    <h4>Related issues</h4>
    <ul>
      {#each pack.relevant_issues as issue (issue.number)}
        <li>
          <a href={`/repos/${repoId}?tab=issues`}>#{issue.number}</a>
          {issue.title} <span class="badge">{issue.state}</span>
        </li>
      {/each}
    </ul>
  {/if}

  {#if pack.relevant_pull_requests.length}
    <h4>Related pull requests</h4>
    <ul>
      {#each pack.relevant_pull_requests as pr (pr.number)}
        <li>
          <a href={`/repos/${repoId}?tab=pull-requests`}>#{pr.number}</a>
          {pr.title} <span class="badge">{pr.state}</span>
        </li>
      {/each}
    </ul>
  {/if}

  {#if pack.relevant_files.length}
    <h4>Relevant files</h4>
    <ul>
      {#each pack.relevant_files as file, i (i)}
        <li><code>{file.path}</code> {#if file.kind}<span class="badge">{file.kind}</span>{/if}</li>
      {/each}
    </ul>
  {/if}

  {#if pack.suggested_next_steps.length}
    <h4>Suggested next steps</h4>
    <ol>
      {#each pack.suggested_next_steps as step, i (i)}<li>{step}</li>{/each}
    </ol>
  {/if}

  {#if pack.excluded_categories.length}
    <p class="muted">Not indexed in mode {pack.mode}: {pack.excluded_categories.join(', ')}</p>
  {/if}
</div>

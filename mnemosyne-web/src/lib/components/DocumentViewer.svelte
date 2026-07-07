<script lang="ts">
  import { marked } from 'marked';
  import type { Document } from '$lib/models';

  let { doc, onClose }: { doc: Document; onClose: () => void } = $props();

  const html = $derived(doc.content ? (marked.parse(doc.content) as string) : null);
</script>

<div class="card viewer">
  <div class="head">
    <strong>{doc.path}</strong>
    <span class="badge">{doc.type}</span>
    <button class="secondary" onclick={onClose}>Close</button>
  </div>
  {#if doc.quarantined}
    <p class="error">
      This document was quarantined by secret scanning — its content is not stored.
    </p>
  {:else if html}
    <!-- eslint-disable-next-line svelte/no-at-html-tags — trusted internal markdown render -->
    <article>{@html html}</article>
  {:else}
    <p class="muted">Empty document.</p>
  {/if}
</div>

<style>
  .viewer {
    margin-top: 1rem;
  }
  .head {
    display: flex;
    gap: 0.75rem;
    align-items: center;
  }
  .head button {
    margin-left: auto;
  }
  article :global(pre) {
    background: var(--surface-2);
    padding: 0.75rem;
    border-radius: 8px;
    overflow-x: auto;
  }
  article :global(code) {
    font-size: 0.85em;
  }
</style>

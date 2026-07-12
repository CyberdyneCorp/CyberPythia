<script lang="ts">
  import { renderMarkdown } from '$lib/markdown';
  import type { Document } from '$lib/models';

  let { doc, onClose }: { doc: Document; onClose: () => void } = $props();

  // Content is GitHub-derived and attacker-controllable; renderMarkdown
  // sanitizes it (DOMPurify) before it reaches {@html}, preventing stored XSS.
  const html = $derived(doc.content ? renderMarkdown(doc.content) : null);
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
    <!-- eslint-disable-next-line svelte/no-at-html-tags — sanitized with DOMPurify above -->
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

<script lang="ts">
  import { goto } from '$app/navigation';
  import { appContext } from '$lib/appContext';

  let error = $state<string | null>(null);

  $effect(() => {
    appContext()
      .auth.completeSignIn()
      .then((returnTo) => {
        window.location.assign(returnTo || '/');
      })
      .catch((e) => {
        error = String(e);
      });
  });
</script>

{#if error}
  <div class="card">
    <h2>Sign-in failed</h2>
    <p class="error">{error}</p>
    <a href="/">Back to home</a>
  </div>
{:else}
  <p class="muted">Completing sign-in…</p>
{/if}

<script lang="ts">
  import '../app.css';
  import { page } from '$app/state';
  import { appContext } from '$lib/appContext';
  import { AuthViewModel } from '$lib/viewmodels/AuthViewModel.svelte';
  import { setContext } from 'svelte';

  let { children } = $props();

  const ctx = appContext();
  const authVm = new AuthViewModel(ctx.auth, ctx.repositoriesApi);
  setContext('app', ctx);
  setContext('authVm', authVm);

  $effect(() => {
    void authVm.initialize();
  });

  const isCallback = $derived(page.url.pathname.startsWith('/auth/'));
</script>

<div class="shell">
  <header>
    <a href="/" class="brand">🧠 Mnemosyne</a>
    <nav>
      <a href="/">Repositories</a>
      <a href="/connections">GitHub Connection</a>
    </nav>
    <div class="session">
      {#if authVm.signedIn}
        <span class="muted">{authVm.displayName}</span>
        <button class="secondary" onclick={() => authVm.signOut()}>Sign out</button>
      {/if}
    </div>
  </header>

  <main>
    {#if isCallback}
      {@render children()}
    {:else if authVm.loading}
      <p class="muted">Loading session…</p>
    {:else if !authVm.signedIn}
      <div class="card gate">
        <h1>Mnemosyne</h1>
        <p class="muted">
          The AI memory layer for Cyberdyne's GitHub organization. Sign in to explore
          repositories, documentation, issues, metrics, and agent context packs.
        </p>
        <button onclick={() => authVm.signIn(page.url.pathname)}>Connect with Cyberdyne</button>
        {#if authVm.signInError}
          <p class="error">Sign-in failed: {authVm.signInError}</p>
        {/if}
      </div>
    {:else if authVm.entitlement === 'denied'}
      <div class="card gate">
        <h1>Access required</h1>
        <p>
          Your Cyberdyne account does not have the <code>mnemosyne</code> entitlement.
          Ask a CyberdyneAuth administrator to grant you access to the Mnemosyne product.
        </p>
      </div>
    {:else}
      {@render children()}
    {/if}
  </main>
</div>

<style>
  .shell {
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 1rem 3rem;
  }
  header {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    padding: 1rem 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.5rem;
  }
  .brand {
    font-weight: 700;
    color: var(--text);
    font-size: 1.05rem;
  }
  nav {
    display: flex;
    gap: 1rem;
    flex: 1;
  }
  .session {
    display: flex;
    gap: 0.75rem;
    align-items: center;
  }
  .gate {
    max-width: 520px;
    margin: 4rem auto;
    text-align: center;
  }
</style>

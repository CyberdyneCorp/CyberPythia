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

  let light = $state(false);

  $effect(() => {
    void authVm.initialize();
    light = document.documentElement.classList.contains('light');
  });

  function toggleTheme() {
    light = !light;
    document.documentElement.classList.toggle('light', light);
    try {
      localStorage.setItem('mnemosyne-theme', light ? 'light' : 'dark');
    } catch {
      // ignore storage failures
    }
  }

  const isCallback = $derived(page.url.pathname.startsWith('/auth/'));

  const NAV = [
    { href: '/', label: 'Repositories', match: (p: string) => p === '/' || p.startsWith('/repos') },
    { href: '/intelligence', label: 'Intelligence', match: (p: string) => p.startsWith('/intelligence') },
    { href: '/connections', label: 'GitHub Connection', match: (p: string) => p.startsWith('/connections') }
  ];
</script>

<div class="app">
  <header>
    <a href="/" class="brand">
      <span class="mark">🧠</span>
      <span>Mnemosyne</span>
    </a>
    {#if authVm.signedIn}
      <nav>
        {#each NAV as item (item.href)}
          <a href={item.href} class="pill" class:active={item.match(page.url.pathname)}>
            {item.label}
          </a>
        {/each}
      </nav>
    {:else}
      <div class="spacer"></div>
    {/if}
    <div class="session">
      <button class="theme" title="Toggle theme" onclick={toggleTheme}>{light ? '☀' : '☾'}</button>
      {#if authVm.signedIn}
        <span class="muted who">{authVm.displayName}</span>
        <button class="signout" onclick={() => authVm.signOut()}>Sign out</button>
      {/if}
    </div>
  </header>

  <main>
    {#if isCallback}
      {@render children()}
    {:else if authVm.loading}
      <div class="center muted">Loading session…</div>
    {:else if !authVm.signedIn}
      <div class="gate">
        <div class="gate-mark">🧠</div>
        <h1>Mnemosyne</h1>
        <p class="eyebrow">Engineering Memory</p>
        <p class="muted lede">
          Everything your organization knows about its code — indexed, scored, and answerable.
        </p>
        <div class="card gate-card">
          <button onclick={() => authVm.signIn(page.url.pathname)}>Connect with Cyberdyne</button>
          {#if authVm.signInError}
            <p class="error">Sign-in failed: {authVm.signInError}</p>
          {/if}
          <p class="sso muted">SSO via Cyberdyne OIDC</p>
        </div>
      </div>
    {:else if authVm.entitlement === 'denied'}
      <div class="gate">
        <div class="gate-mark warn-mark">✳</div>
        <h1>Access required</h1>
        <p class="muted lede">
          You're signed in, but your account hasn't been granted access to Mnemosyne yet. Ask a
          CyberdyneAuth administrator to grant you the <code>mnemosyne</code> entitlement.
        </p>
      </div>
    {:else}
      {@render children()}
    {/if}
  </main>
</div>

<style>
  header {
    display: flex;
    align-items: center;
    gap: 1.75rem;
    height: 52px;
    padding: 0 1.4rem;
    border-bottom: 1px solid var(--line);
    background: var(--bg2);
    position: sticky;
    top: 0;
    z-index: 20;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    font-weight: 600;
    color: var(--tx);
    font-size: 0.95rem;
    letter-spacing: -0.01em;
  }
  .brand .mark {
    font-size: 1.1rem;
  }
  nav {
    display: flex;
    gap: 0.25rem;
    flex: 1;
  }
  .spacer {
    flex: 1;
  }
  .pill {
    padding: 0.35rem 0.7rem;
    border-radius: 6px;
    font-size: 0.83rem;
    font-weight: 500;
    color: var(--tx2);
  }
  .pill:hover {
    color: var(--tx);
  }
  .pill.active {
    background: var(--acb);
    color: var(--ac);
  }
  .session {
    display: flex;
    align-items: center;
    gap: 0.85rem;
  }
  .theme {
    background: var(--panel);
    color: var(--tx2);
    border: 1px solid var(--line);
    border-radius: 6px;
    width: 30px;
    height: 28px;
    padding: 0;
    font-size: 0.85rem;
    font-weight: 400;
  }
  .who {
    font-size: 0.83rem;
  }
  .signout {
    font-size: 0.8rem;
    color: var(--tx3);
    background: none;
    border: none;
    padding: 0;
    font-weight: 400;
  }
  .signout:hover {
    color: var(--tx);
    opacity: 1;
  }
  main {
    max-width: 1180px;
    margin: 0 auto;
    padding: 1.6rem 1.4rem 4rem;
  }
  .center {
    padding: 4rem 0;
    text-align: center;
  }
  .gate {
    max-width: 400px;
    margin: 4.5rem auto 0;
    text-align: center;
  }
  .gate-mark {
    width: 58px;
    height: 58px;
    margin: 0 auto 1rem;
    border-radius: 14px;
    background: var(--panel);
    border: 1px solid var(--line2);
    box-shadow: 0 0 0 6px var(--acb), var(--sh);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.7rem;
  }
  .warn-mark {
    box-shadow: none;
    color: var(--ac);
    background: var(--acb);
    border-color: var(--ac);
  }
  .gate h1 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 700;
  }
  .gate .eyebrow {
    color: var(--ac);
    margin: 0.35rem 0 0;
  }
  .lede {
    font-size: 0.85rem;
    line-height: 1.55;
    margin: 0.8rem auto 0;
    max-width: 320px;
  }
  .gate-card {
    margin-top: 1.4rem;
    padding: 1.5rem;
  }
  .gate-card button {
    width: 100%;
  }
  .sso {
    font-size: 0.72rem;
    margin: 0.9rem 0 0;
  }
</style>

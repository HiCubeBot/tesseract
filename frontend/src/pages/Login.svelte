<script lang="ts">
  import { session } from '../lib/session.svelte';
  import { router } from '../lib/router.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import { api, type DeviceInfo } from '../lib/api';

  let username = $state('admin');
  let password = $state('');
  let remember = $state(false);
  let error = $state('');
  let busy = $state(false);
  let device = $state<DeviceInfo | null>(null);

  api.get<DeviceInfo>('/auth/device').then(
    (d) => (device = d),
    () => (device = null)
  );

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    error = '';
    busy = true;
    try {
      await session.login(username, password, remember);
      password = '';
      if (router.path === 'login') router.go('');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Anmeldung fehlgeschlagen';
    } finally {
      busy = false;
    }
  }
</script>

<div class="login">
  <section class="intro">
    <div class="brand">
      <div class="logo">
        <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0E1014" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h18v18H3z"></path><path d="M8 8h8v8H8z"></path><path d="M3 3l5 5M21 3l-5 5M3 21l5-5M21 21l-5-5"></path></svg>
      </div>
      <div class="stack">
        <span class="brand-name">Tesseract</span>
        <span class="muted">Caddy-Verwaltung</span>
      </div>
    </div>
    <div class="claim">
      <h1>Ein Webinterface für alle deine Caddy-Nodes.</h1>
      <p class="muted">Öffentliche Hosts mit Let's Encrypt, private Dienste nur für freigegebene Geräte – zentral verwaltet.</p>
    </div>
    <div class="hint">
      <span class="hint-icon"><Icon name="lock" size={16} strokeWidth={2} /></span>
      <span class="muted">
        <strong>Doppelt geschützt.</strong> Mit eingeschaltetem Admin-Zertifikat ist diese Seite nur von
        Admin-Geräten erreichbar – das Passwort ist die zweite Hürde.
      </span>
    </div>
  </section>

  <main>
    <form onsubmit={submit}>
      <div class="head">
        <h2>Anmelden</h2>
        {#if device?.admin_device}
          <span class="detected"><span class="dot"></span>Admin-Gerät erkannt · {device.admin_device}</span>
        {:else if device?.certificate}
          <span class="detected other">Zertifikat erkannt – kein Admin-Gerät</span>
        {/if}
      </div>

      <label>
        Benutzername
        <input type="text" autocomplete="username" required bind:value={username} />
      </label>

      <label>
        Passwort
        <!-- svelte-ignore a11y_autofocus -->
        <input type="password" autocomplete="current-password" required autofocus bind:value={password} aria-invalid={error ? 'true' : undefined} />
      </label>

      <label class="check">
        <input type="checkbox" bind:checked={remember} />
        Auf diesem Gerät 30 Tage angemeldet bleiben
      </label>

      {#if error}<p class="error" role="alert">{error}</p>{/if}

      <button type="submit" disabled={busy}>{busy ? 'Anmelden …' : 'Anmelden'}</button>

      <p class="muted small">
        Passwort vergessen? Zurücksetzen geht nur auf dem Controller selbst:
        <code>tesseract admin reset</code>
      </p>
    </form>
  </main>
</div>

<style>
  .login {
    min-height: 100vh;
    display: flex;
    flex-wrap: wrap;
    font-size: 15px;
  }
  .intro {
    flex: 1 1 480px;
    min-width: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 40px;
    padding: 48px 56px;
    background: var(--sidebar);
    border-right: 1px solid var(--border);
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .logo {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: var(--text);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .stack {
    display: flex;
    flex-direction: column;
  }
  .brand-name {
    font-weight: 700;
    font-size: 18px;
  }
  .muted {
    color: var(--text-muted);
  }
  .small {
    font-size: 13px;
    line-height: 1.5;
    margin: 0;
  }
  .claim {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 480px;
  }
  h1 {
    margin: 0;
    font-size: 40px;
    line-height: 1.1;
    letter-spacing: -0.02em;
  }
  .claim p {
    margin: 0;
    line-height: 1.6;
  }
  .hint {
    display: flex;
    gap: 12px;
    padding: 14px 16px;
    border-radius: var(--radius-lg);
    background: var(--surface);
    border: 1px solid var(--border);
    max-width: 480px;
    font-size: 14px;
    line-height: 1.5;
  }
  .hint strong {
    color: var(--text);
    font-weight: 600;
  }
  .hint-icon {
    width: 32px;
    height: 32px;
    flex-shrink: 0;
    border-radius: var(--radius);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: rgba(139, 124, 246, 0.18);
    color: #c9c1ff;
  }
  main {
    flex: 1 1 480px;
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 48px 32px;
  }
  form {
    width: 100%;
    max-width: 400px;
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  h2 {
    margin: 0;
    font-size: 28px;
    letter-spacing: -0.02em;
  }
  .head {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .detected {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    align-self: flex-start;
    padding: 5px 12px;
    border-radius: var(--radius-pill);
    background: var(--ok-soft);
    color: var(--ok-text);
    font-size: 13px;
    font-weight: 600;
  }
  .detected.other {
    background: var(--surface-raised);
    color: var(--text-muted);
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--ok);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 14px;
    color: var(--text-muted);
  }
  input[type='text'],
  input[type='password'] {
    min-height: 48px;
    padding: 0 14px;
    border-radius: var(--radius-md);
    background: var(--surface);
    border: 1px solid var(--border-input);
    color: var(--text);
    font: inherit;
  }
  input:focus {
    border-color: var(--accent);
    outline: none;
  }
  .check {
    flex-direction: row;
    align-items: center;
    gap: 10px;
    min-height: 44px;
    color: var(--text);
    cursor: pointer;
  }
  .check input {
    width: 18px;
    height: 18px;
    margin: 0;
    accent-color: var(--accent);
  }
  button {
    min-height: 50px;
    border-radius: var(--radius-md);
    border: none;
    background: var(--text);
    color: var(--bg);
    font: inherit;
    font-weight: 600;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.6;
    cursor: progress;
  }
  .error {
    margin: 0;
    padding: 10px 12px;
    border-radius: var(--radius);
    background: var(--bad-soft);
    color: var(--bad-text);
    font-size: 14px;
  }
  code {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-soft);
  }
  @media (max-width: 640px) {
    .intro {
      padding: 32px 16px;
    }
    h1 {
      font-size: 30px;
    }
    main {
      padding: 32px 16px;
    }
  }
</style>

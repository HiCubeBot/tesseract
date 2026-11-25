<script lang="ts">
  import { t } from '../lib/i18n';
  /**
   * Öffentliche Seite /v – Gäste verlängern ihr Gerät selbst. Ausweis ist das noch gültige
   * Gerätezertifikat, das der Browser beim Aufruf vorzeigt.
   */
  import Icon from '../lib/components/Icon.svelte';
  import { ApiError, base64ToBytes, downloadFile, fetchRetry, formatDay } from '../lib/api';
  import { detectPlatform, INSTALL_STEPS, type Platform } from '../lib/install';

  interface RenewStatus {
    enabled: boolean;
    recognized: boolean;
    device: string | null;
    person: string | null;
    not_after: string | null;
    days_left: number | null;
    can_renew: boolean;
    opens_at: string | null;
    reason: string | null;
  }

  interface Renewed {
    filename: string;
    password: string;
    p12_base64: string;
    not_after: string;
  }

  let status = $state<RenewStatus | null>(null);
  let cert = $state<Renewed | null>(null);
  let error = $state('');
  let busy = $state(false);
  let downloaded = $state(false);
  let platform = $state<Platform>(detectPlatform());

  async function call<T>(method: string): Promise<T> {
    const res = await fetchRetry('/api/renew', { method, credentials: 'omit', referrerPolicy: 'no-referrer' });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new ApiError(res.status, typeof data?.detail === 'string' ? data.detail : t('Fehler {0}', res.status));
    return data as T;
  }

  async function load() {
    try {
      status = await call<RenewStatus>('GET');
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  async function renew() {
    busy = true;
    error = '';
    try {
      cert = await call<Renewed>('POST');
      download();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      busy = false;
    }
  }

  function download() {
    if (!cert) return;
    downloadFile(cert.filename, base64ToBytes(cert.p12_base64), 'application/x-pkcs12');
    downloaded = true;
  }

  // Zertifikat nur im Speicher – vor dem Verlassen warnen, solange es nicht geladen ist
  $effect(() => {
    if (!cert || downloaded) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  });

  const guide = $derived(INSTALL_STEPS[platform]);
</script>

<div class="page">
  <header class="brand">
    <div class="logo">
      <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" style="stroke: var(--bg)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h18v18H3z"></path><path d="M8 8h8v8H8z"></path><path d="M3 3l5 5M21 3l-5 5M3 21l5-5M21 21l-5-5"></path></svg>
    </div>
    <span class="brand-name">{t('Tesseract')}</span>
  </header>

  <main class="card">
    {#if !status && !error}
      <p class="muted">{t('Prüfe dein Gerät …')}</p>
    {:else if cert}
      <span class="eyebrow">{t('Gerät verlängert')}</span>
      <h1>{t('Neues Zertifikat installieren')}</h1>
      <p class="muted">
        {t('Das alte Zertifikat gilt ab sofort nicht mehr. Installiere das neue jetzt – es wird nur einmal ausgegeben. Das alte kannst du danach aus dem Gerät löschen.')}
      </p>
      <div class="pw">
        <span class="muted small">{t('Passwort für die Installation')}</span>
        <code class="mono">{cert.password}</code>
      </div>
      <button type="button" class="secondary" onclick={download}>
        <Icon name="download" size={16} strokeWidth={2} /> {t('Erneut herunterladen')}
      </button>
      <section class="guide" aria-labelledby="guide-title">
        <label class="field">
          {t('Anleitung für')}
          <select class="input" bind:value={platform}>
            {#each Object.entries(INSTALL_STEPS) as [k, v] (k)}<option value={k}>{v.title}</option>{/each}
          </select>
        </label>
        <h2 id="guide-title" class="visually-hidden">{t('Anleitung')}</h2>
        <ol>{#each guide.steps as step, i (i)}<li>{step}</li>{/each}</ol>
        {#if guide.browser}<p class="muted small">{guide.browser}</p>{/if}
      </section>
      <p class="muted small">{t('Das neue Zertifikat gilt bis {0}.', formatDay(cert.not_after))}</p>
    {:else if status}
      <span class="eyebrow">{t('Gerät verlängern')}</span>
      {#if status.recognized && status.device}
        <h1>{status.device}</h1>
        <p class="muted">
          {t('{0} · gültig bis {1}', status.person, formatDay(status.not_after ?? ''))}
          {#if status.days_left !== null}{status.days_left === 1 ? t('· noch 1 Tag') : t('· noch {0} Tage', status.days_left)}{/if}
        </p>
      {:else}
        <h1>{t('Gerät nicht erkannt')}</h1>
      {/if}

      {#if status.can_renew}
        <p>{t('Mit einem Klick bekommst du ein neues Zertifikat für dieses Gerät. Deine Freigaben bleiben gleich.')}</p>
        {#if error}<p class="error" role="alert">{error}</p>{/if}
        <button type="button" class="primary" disabled={busy} onclick={renew}>
          <Icon name="refresh" size={16} strokeWidth={2} /> {busy ? t('Erzeuge …') : t('Jetzt verlängern')}
        </button>
      {:else}
        <p class="info">
          {status.reason}
          {#if status.opens_at}{t('Das ist ab {0} möglich – öffne diesen Link dann einfach noch einmal.', formatDay(status.opens_at))}{/if}
        </p>
        {#if !status.recognized && status.enabled}
          <p class="muted small">
            {t('Hat der Browser nicht nach einem Zertifikat gefragt? Dann ist das Zertifikat auf diesem Gerät nicht (mehr) installiert oder schon abgelaufen. In dem Fall bitte an die Person wenden, die dich eingeladen hat.')}
          </p>
        {/if}
      {/if}
    {:else}
      <h1>{t('Fehler')}</h1>
      <p class="error" role="alert">{error}</p>
    {/if}
  </main>
</div>

<style>
  .page {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
    padding: 32px 16px;
    font-size: 15px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .logo {
    width: 34px;
    height: 34px;
    border-radius: 9px;
    background: var(--text);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .brand-name {
    font-weight: 700;
    font-size: 17px;
  }
  main {
    width: 100%;
    max-width: 480px;
    gap: 16px;
    padding: 24px;
  }
  .eyebrow {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
  }
  h1 {
    margin: 0;
    font-size: 26px;
    line-height: 1.2;
    letter-spacing: -0.02em;
    overflow-wrap: anywhere;
  }
  p {
    margin: 0;
    line-height: 1.55;
  }
  .small {
    font-size: 13px;
  }
  .info {
    padding: 12px 14px;
    border-radius: var(--radius-md);
    background: var(--bg);
    border: 1px solid var(--border);
  }
  button {
    min-height: 50px;
    border-radius: var(--radius-md);
    font: inherit;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }
  .primary {
    border: none;
    background: var(--text);
    color: var(--bg);
  }
  .secondary {
    border: 1px solid var(--border-input);
    background: transparent;
    color: var(--text);
  }
  button:disabled {
    opacity: 0.6;
    cursor: progress;
  }
  .error {
    padding: 10px 12px;
    border-radius: var(--radius);
    background: var(--bad-soft);
    color: var(--bad-text);
    font-size: 14px;
  }
  .pw {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 14px;
    border-radius: var(--radius-md);
    background: var(--bg);
    border: 1px solid var(--accent);
  }
  .pw code {
    font-size: 20px;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: var(--text);
    overflow-wrap: anywhere;
  }
  .guide {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  ol {
    margin: 0;
    padding-left: 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    line-height: 1.5;
  }
</style>

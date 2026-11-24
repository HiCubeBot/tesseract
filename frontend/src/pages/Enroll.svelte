<script lang="ts">
  /**
   * Öffentliche Einladungsseite (/e/<token>) – der einzige Teil von Tesseract,
   * der ohne Zertifikat und ohne Anmeldung erreichbar ist.
   */
  import Icon from '../lib/components/Icon.svelte';
  import {
    ApiError,
    base64ToBytes,
    downloadFile,
    fetchRetry,
    formatDay,
    PLATFORMS,
    type GuestCertificate,
    type PublicInvite
  } from '../lib/api';
  import { detectPlatform, INSTALL_STEPS, suggestedName, type Platform } from '../lib/install';

  interface Props {
    token: string;
  }

  let { token }: Props = $props();

  type Stage = 'loading' | 'invalid' | 'register' | 'waiting' | 'rejected' | 'install' | 'done';

  let stage = $state<Stage>('loading');
  let info = $state<PublicInvite | null>(null);
  let error = $state('');
  let platform = $state<Platform>(detectPlatform());
  let deviceName = $state('');
  let code = $state('');
  let busy = $state(false);
  let request = $state<{ id: number; secret: string } | null>(null);
  let cert = $state<GuestCertificate | null>(null);
  let downloaded = $state(false);

  const storageKey = $derived(`tesseract-enroll-${token.slice(0, 12)}`);

  async function call<T>(method: string, path: string, body?: unknown, secret?: string): Promise<T> {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (secret) headers['X-Enroll-Secret'] = secret;
    const res = await fetchRetry(`/api/enroll/${encodeURIComponent(token)}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: 'omit',
      referrerPolicy: 'no-referrer'
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new ApiError(res.status, data?.detail && typeof data.detail === 'string' ? data.detail : `Fehler ${res.status}`);
    return data as T;
  }

  function remember(r: { id: number; secret: string } | null) {
    try {
      if (r) sessionStorage.setItem(storageKey, JSON.stringify(r));
      else sessionStorage.removeItem(storageKey);
    } catch {
      /* privater Modus – dann eben ohne */
    }
  }

  async function start() {
    try {
      info = await call<PublicInvite>('GET', '');
      deviceName = suggestedName(platform, info.person_name);
    } catch {
      stage = 'invalid';
      return;
    }
    try {
      const saved = sessionStorage.getItem(storageKey);
      if (saved) {
        request = JSON.parse(saved);
        await poll();
        return;
      }
    } catch {
      /* ignorieren */
    }
    stage = 'register';
  }
  start();

  async function register(e: SubmitEvent) {
    e.preventDefault();
    busy = true;
    error = '';
    try {
      const r = await call<{ enrollment_id: number; secret: string }>('POST', '/register', {
        device_name: deviceName,
        platform,
        code
      });
      request = { id: r.enrollment_id, secret: r.secret };
      remember(request);
      stage = 'waiting';
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
      if (err instanceof ApiError && err.status === 404) stage = 'invalid';
    } finally {
      busy = false;
    }
  }

  async function poll() {
    if (!request) return;
    try {
      const s = await call<{ status: string }>('GET', `/requests/${request.id}`, undefined, request.secret);
      if (s.status === 'pending') stage = 'waiting';
      else if (s.status === 'rejected') {
        stage = 'rejected';
        remember(null);
      } else if (s.status === 'approved') stage = 'install';
      else if (s.status === 'delivered') {
        stage = 'done';
        remember(null);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        remember(null);
        stage = 'register';
      }
    }
  }

  // Während der Wartezeit alle 4 Sekunden nachsehen
  $effect(() => {
    if (stage !== 'waiting') return;
    const t = setInterval(poll, 4000);
    return () => clearInterval(t);
  });

  async function fetchCertificate() {
    if (!request) return;
    busy = true;
    error = '';
    try {
      cert = await call<GuestCertificate>('POST', `/requests/${request.id}/certificate`, {}, request.secret);
      remember(null);
      download();
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
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
  const services = $derived(cert?.services ?? info?.services ?? []);
</script>

<div class="page">
  <header class="brand">
    <div class="logo">
      <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" style="stroke: var(--bg)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h18v18H3z"></path><path d="M8 8h8v8H8z"></path><path d="M3 3l5 5M21 3l-5 5M3 21l5-5M21 21l-5-5"></path></svg>
    </div>
    <span class="brand-name">Tesseract</span>
  </header>

  <main class="card">
    {#if stage === 'loading'}
      <p class="muted">Lade Einladung …</p>
    {:else if stage === 'invalid'}
      <h1>Einladung nicht gültig</h1>
      <p class="muted">Der Link ist abgelaufen, wurde widerrufen oder ist falsch. Bitte frag nach einer neuen Einladung.</p>
    {:else if info}
      {#if stage === 'register'}
        <span class="eyebrow">Schritt 1 von 2 · Gerät registrieren</span>
        <h1>Hallo {info.person_name.split(/\s+/)[0]},<br />du wurdest eingeladen.</h1>
        <p class="muted">
          Diese Dienste sind privat und nur von freigeschalteten Geräten aus erreichbar. Dafür bekommt dein Gerät
          gleich ein eigenes Zertifikat – wie ein Schlüssel, den nur es selbst hat.
        </p>
        {#if services.length}
          <div class="services">
            <span class="muted small">Danach kommst du auf:</span>
            <ul>{#each services as s (s)}<li class="mono">{s}</li>{/each}</ul>
          </div>
        {/if}
        <form onsubmit={register}>
          <label class="field">
            Name dieses Geräts
            <input class="input" required maxlength="64" bind:value={deviceName} />
          </label>
          <label class="field">
            Gerät
            <select class="input" bind:value={platform}>
              {#each Object.entries(PLATFORMS) as [k, v] (k)}<option value={k}>{v}</option>{/each}
            </select>
            <span class="muted small">automatisch erkannt</span>
          </label>
          <label class="field">
            Bestätigungscode
            <input class="input mono code" required inputmode="numeric" autocomplete="one-time-code" placeholder="123 456" maxlength="16" bind:value={code} />
            <span class="muted small">Den Code hast du separat bekommen (z. B. am Telefon).</span>
          </label>
          {#if error}<p class="error" role="alert">{error}</p>{/if}
          <button type="submit" class="primary" disabled={busy}>{busy ? 'Sende …' : 'Gerät registrieren'}</button>
        </form>
        <p class="muted small">Noch {info.slots_left} von {info.max_devices} Geräten frei · Einladung gültig bis {formatDay(info.expires_at)}</p>
      {:else if stage === 'waiting'}
        <span class="eyebrow">Schritt 1 von 2 · Gerät registrieren</span>
        <h1>Fast geschafft</h1>
        <div class="wait" aria-live="polite">
          <span class="spinner" aria-hidden="true"></span>
          <p>Deine Anfrage ist angekommen. Sobald sie freigegeben ist, geht es hier automatisch weiter.</p>
        </div>
        <p class="muted small">Du kannst diese Seite offen lassen.</p>
      {:else if stage === 'rejected'}
        <h1>Anfrage abgelehnt</h1>
        <p class="muted">Dein Gerät wurde nicht freigegeben. Bei Fragen wende dich an die Person, die dich eingeladen hat.</p>
        <button type="button" class="secondary" onclick={() => (stage = 'register')}>Noch einmal versuchen</button>
      {:else if stage === 'install' || stage === 'done'}
        <span class="eyebrow">Schritt 2 von 2 · Zertifikat installieren</span>
        {#if stage === 'done' && !cert}
          <h1>Zertifikat bereits abgeholt</h1>
          <p class="muted">Für dieses Gerät wurde das Zertifikat schon heruntergeladen. Ist es verloren gegangen, registriere das Gerät einfach neu.</p>
        {:else if !cert}
          <h1>Dein Gerät ist freigegeben</h1>
          <p class="muted">Lade jetzt dein persönliches Zertifikat. Es wird nur einmal ausgegeben – also am besten direkt installieren.</p>
          {#if error}<p class="error" role="alert">{error}</p>{/if}
          <button type="button" class="primary" disabled={busy} onclick={fetchCertificate}>
            <Icon name="download" size={16} strokeWidth={2} /> {busy ? 'Erzeuge …' : 'Zertifikat herunterladen'}
          </button>
        {:else}
          <h1>Zertifikat installieren</h1>
          <div class="pw">
            <span class="muted small">Passwort für die Installation</span>
            <code class="mono">{cert.password}</code>
          </div>
          <button type="button" class="secondary" onclick={download}>
            <Icon name="download" size={16} strokeWidth={2} /> Erneut herunterladen
          </button>

          <section class="guide" aria-labelledby="guide-title">
            <label class="field">
              Anleitung für
              <select class="input" bind:value={platform}>
                {#each Object.entries(INSTALL_STEPS) as [k, v] (k)}<option value={k}>{v.title}</option>{/each}
              </select>
            </label>
            <h2 id="guide-title" class="visually-hidden">Anleitung</h2>
            <ol>{#each guide.steps as step, i (i)}<li>{step}</li>{/each}</ol>
            {#if guide.browser}<p class="muted small">{guide.browser}</p>{/if}
          </section>

          {#if services.length}
            <section class="services">
              <span class="muted small">Hat es geklappt? Nach der Installation hier testen:</span>
              <ul>
                {#each services as s (s)}
                  <li><a class="mono" href={`https://${s}`} target="_blank" rel="noopener">{s} öffnen</a></li>
                {/each}
              </ul>
            </section>
          {/if}

          <p class="muted small">
            Das Zertifikat gilt bis {formatDay(cert.not_after)}.
            {#if cert.slots_left > 0}Noch ein Gerät? Öffne denselben Link auf dem anderen Gerät – {cert.slots_left} Platz/Plätze frei.{/if}
          </p>
          {#if cert.renew_url}
            <p class="muted small">
              Kurz vor Ablauf kannst du das Zertifikat selbst verlängern: öffne dann auf diesem Gerät
              <a class="mono" href={cert.renew_url}>{cert.renew_url}</a> – am besten jetzt als Lesezeichen speichern.
            </p>
          {/if}
        {/if}
      {/if}
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
  h1 {
    margin: 0;
    font-size: 26px;
    line-height: 1.2;
    letter-spacing: -0.02em;
  }
  p {
    margin: 0;
    line-height: 1.55;
  }
  .small {
    font-size: 13px;
  }
  form {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .code {
    font-size: 20px;
    letter-spacing: 0.1em;
  }
  .services ul {
    margin: 6px 0 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .services li {
    font-size: 14px;
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
  .wait {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px;
    border-radius: var(--radius-md);
    background: var(--bg);
  }
  .spinner {
    width: 22px;
    height: 22px;
    flex-shrink: 0;
    border-radius: 50%;
    border: 3px solid var(--surface-raised);
    border-top-color: var(--accent);
    animation: spin 0.9s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .spinner {
      animation: none;
    }
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

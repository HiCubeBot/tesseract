<script lang="ts">
  import { router } from './lib/router.svelte';
  import { session } from './lib/session.svelte';
  import { routes, aliases, matchPage } from './routes';
  import ScreenIndex from './ScreenIndex.svelte';
  import LoginPage from './pages/Login.svelte';
  import Toasts from './lib/components/Toasts.svelte';
  import EnrollPage from './pages/Enroll.svelte';
  import RenewPage from './pages/Renew.svelte';
  import StatusPage from './pages/StatusPublic.svelte';
  import { homeFor, pageAllowed } from './lib/permissions';

  // Öffentliche Einladungsseite /e/<token> – ohne Anmeldung, ohne Hash-Router
  const enrollToken = window.location.pathname.match(/^\/e\/([A-Za-z0-9_-]{8,64})\/?$/)?.[1] ?? null;

  // Gäste verlängern ihr Gerät selbst: /v – ebenfalls ohne Anmeldung
  const renewPage = /^\/v\/?$/.test(window.location.pathname);

  // Öffentliche Statusseite des Uptime-Monitors: /status – ohne Anmeldung
  const statusPage = /^\/status\/?$/.test(window.location.pathname);

  if (!enrollToken && !renewPage && !statusPage) session.check();

  const path = $derived(aliases[router.path] ?? router.path);
  const designPath = $derived(path.startsWith('design/') ? path.slice('design/'.length) : null);
  const match = $derived(designPath === null ? matchPage(path) : null);
  const prototype = $derived(
    match ? undefined : routes.find((r) => r.path === (designPath ?? path))
  );
  const needsLogin = $derived(session.checked && !session.user && !match?.page.public);
  const title = $derived(match?.page.title ?? prototype?.title ?? 'Screens');

  // „Eigene Dienste“ starten in der Hostliste statt auf der (gesperrten) Übersicht
  $effect(() => {
    if (session.user && path === '' && !pageAllowed(session.user.role, '')) router.go('hosts');
  });

  $effect(() => {
    document.title = statusPage
      ? 'Status'
      : enrollToken
        ? 'Einladung – Tesseract'
        : renewPage
          ? 'Gerät verlängern – Tesseract'
          : (needsLogin ? 'Anmelden' : title) + ' – Tesseract';
  });
</script>

{#if statusPage}
  <StatusPage />
{:else if enrollToken}
  <EnrollPage token={enrollToken} />
{:else if renewPage}
  <RenewPage />
{:else if !session.checked}
  <div class="loading" aria-busy="true">Lade …</div>
{:else if needsLogin}
  <LoginPage />
{:else if match && session.user && !pageAllowed(session.user.role, match.page.pattern)}
  <div class="loading denied" role="alert">
    <p>Diese Seite ist für deine Rolle nicht freigegeben.</p>
    <a href={homeFor(session.user.role)}>Zur Startseite</a>
  </div>
{:else if match}
  {#key path}
    <match.page.component params={match.params} />
  {/key}
{:else if prototype}
  <div class="proto-banner" role="note">
    Prototyp aus dem Design – zeigt Beispieldaten, noch ohne Funktion.
    <a href="#/screens">Alle Screens</a>
  </div>
  {#key prototype.path}
    <prototype.component />
  {/key}
{:else}
  <ScreenIndex />
{/if}

<Toasts />

<style>
  .denied {
    flex-direction: column;
    gap: 8px;
  }
  .loading {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
  }
  .proto-banner {
    position: sticky;
    top: 0;
    z-index: 40;
    display: flex;
    flex-wrap: wrap;
    gap: 6px 12px;
    justify-content: center;
    padding: 8px 16px;
    background: var(--warn-soft);
    border-bottom: 1px solid rgba(229, 164, 67, 0.45);
    color: var(--warn-text);
    font-size: 13px;
    font-weight: 500;
  }
</style>

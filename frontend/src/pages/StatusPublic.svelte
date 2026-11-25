<script lang="ts">
  import { locale, t } from '../lib/i18n';
  // Öffentliche Statusseite (/status): ohne Anmeldung, nur freigegebene Dienste mit Namen und
  // Erreichbarkeit der letzten 90 Tage. Lädt jede Minute neu.
  import { onDestroy } from 'svelte';
  import UptimeBars from '../lib/components/UptimeBars.svelte';
  import { fetchRetry } from '../lib/api';

  interface Service {
    name: string;
    status: 'up' | 'down' | 'unknown' | 'paused';
    since: string | null;
    pct: number | null;
    days: { day: string; pct: number | null; down_minutes: number }[];
  }
  interface Status {
    checked_at: string;
    overall: 'ok' | 'partial' | 'down' | 'none' | 'pending';
    services: Service[];
  }

  let data = $state<Status | null>(null);
  let error = $state('');

  async function load() {
    try {
      const r = await fetchRetry('/api/status', { headers: { Accept: 'application/json' } });
      if (r.status === 404) throw new Error(t('Diese Statusseite ist nicht eingeschaltet.'));
      if (!r.ok) throw new Error(t('Status nicht abrufbar ({0})', r.status));
      data = await r.json();
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();
  const timer = setInterval(load, 60_000);
  onDestroy(() => clearInterval(timer));

  const OVERALL = {
    ok: { text: t('Alle Dienste laufen'), tone: 'ok' },
    partial: { text: t('Einzelne Dienste sind gestört'), tone: 'warn' },
    down: { text: t('Alle Dienste sind gestört'), tone: 'bad' },
    none: { text: t('Keine Dienste freigegeben'), tone: 'none' },
    pending: { text: t('Noch nicht geprüft'), tone: 'none' }
  } as const;
  const LABEL = { up: t('läuft'), down: t('gestört'), unknown: 'unbekannt', paused: 'pausiert' } as const;
  const pct = (v: number | null) => (v === null ? '–' : `${v.toLocaleString(locale, { maximumFractionDigits: 2 })} %`);
</script>

<div class="page">
  <main>
    <header>
      <div class="logo" aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          ><path d="M3 3h18v18H3z"></path><path d="M8 8h8v8H8z"></path><path d="M3 3l5 5M21 3l-5 5M3 21l5-5M21 21l-5-5"></path></svg
        >
      </div>
      <h1>{t('Status')}</h1>
    </header>

    {#if error}
      <p class="banner bad">{error}</p>
    {:else if data}
      {@const o = OVERALL[data.overall]}
      <p class="banner {o.tone}">{o.text}</p>
      <ul class="services">
        {#each data.services as s (s.name)}
          <li>
            <div class="top">
              <span class="name">{s.name}</span>
              <span class="state {s.status}">{LABEL[s.status]}</span>
            </div>
            <UptimeBars days={s.days} label={t('Erreichbarkeit von {0} in den letzten 90 Tagen', s.name)} height={28} />
            <div class="bottom">
              <span>{t('vor 90 Tagen')}</span>
              <span>{t('{0} erreichbar', pct(s.pct))}</span>
              <span>{t('heute')}</span>
            </div>
          </li>
        {/each}
      </ul>
      <p class="foot">
        {t('Zuletzt geprüft {0} · aktualisiert sich jede Minute', new Date(data.checked_at).toLocaleString(locale, { dateStyle: 'short', timeStyle: 'short' }))}
      </p>
    {:else}
      <p class="foot">{t('Lädt …')}</p>
    {/if}
  </main>
</div>

<style>
  .page {
    min-height: 100vh;
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-sans);
    padding: 40px 16px;
    box-sizing: border-box;
  }
  main {
    max-width: 760px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  header {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .logo {
    width: 34px;
    height: 34px;
    border-radius: 9px;
    background: var(--text);
    color: var(--bg);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  h1 {
    margin: 0;
    font-size: 24px;
  }
  .banner {
    margin: 0;
    padding: 14px 18px;
    border-radius: var(--radius-lg);
    font-weight: 600;
    border: 1px solid var(--border);
    background: var(--surface);
  }
  .banner.ok {
    border-color: rgba(47, 158, 107, 0.5);
    background: rgba(47, 158, 107, 0.1);
    color: var(--ok-text);
  }
  .banner.warn {
    border-color: rgba(217, 162, 58, 0.5);
    background: rgba(217, 162, 58, 0.1);
    color: var(--warn-text);
  }
  .banner.bad {
    border-color: rgba(217, 96, 74, 0.5);
    background: rgba(217, 96, 74, 0.1);
    color: var(--bad-text);
  }
  .services {
    list-style: none;
    margin: 0;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--surface);
  }
  .services li {
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .services li + li {
    border-top: 1px solid var(--border);
  }
  .top,
  .bottom {
    display: flex;
    justify-content: space-between;
    gap: 10px;
  }
  .name {
    font-weight: 600;
  }
  .state {
    font-size: 13px;
    color: var(--text-muted);
  }
  .state.up {
    color: var(--ok-text);
  }
  .state.down {
    color: var(--bad-text);
  }
  .bottom {
    font-size: 11px;
    color: var(--text-muted);
  }
  .foot {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
  }
</style>

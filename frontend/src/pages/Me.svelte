<script lang="ts">
  import { t } from '../lib/i18n';
  // „Mein Zugang“: für Personen, die per Gerätezertifikat angemeldet sind – Rolle, eigene
  // Geräte und die Hosts, für die sie freigegeben sind.
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import { api, DEVICE_STATUS, formatDay, UI_ROLES, UI_ROLE_HINTS, type MyAccess } from '../lib/api';
  import { session } from '../lib/session.svelte';

  let data = $state<MyAccess | null>(null);
  let error = $state('');

  if (session.viaCert) {
    api.get<MyAccess>('/me/devices').then(
      (d) => (data = d),
      (e) => (error = e instanceof Error ? e.message : String(e))
    );
  }
</script>

<AppShell active="me">
  <PageHeader title={t('Mein Zugang')} subtitle={t('Angemeldet per Gerätezertifikat – ohne Passwort.')} />

  {#if !session.viaCert}
    <Alert tone="info" title={t('Nur für Personen')} text={t('Diese Seite gibt es für Personen, die Tesseract per Gerätezertifikat öffnen.')} />
  {/if}
  {#if error}<Alert tone="bad" title={t('Fehler')} text={error} />{/if}

  {#if data}
    <section class="card" aria-labelledby="role-title">
      <h2 id="role-title">{data.person} · {UI_ROLES[data.role]}</h2>
      <p class="muted small">{UI_ROLE_HINTS[data.role]}</p>
      <p class="small">{t('Dieses Gerät:')} <strong>{data.current_device}</strong>{t('. Wird es gesperrt oder läuft sein Zertifikat ab, ist der Zugriff sofort weg.')}</p>
    </section>

    <section class="card" aria-labelledby="dev-title">
      <h2 id="dev-title">{t('Meine Geräte')}</h2>
      <ul class="list">
        {#each data.devices as d (d.id)}
          <li>
            <span class="grow">
              <strong>{d.name}</strong>
              {#if d.name === data.current_device}<span class="muted small"> {t('· dieses Gerät')}</span>{/if}
              <span class="muted small block">{t('gültig bis {0}', d.unlimited ? 'unbegrenzt' : formatDay(d.not_after))}</span>
            </span>
            <StatusPill tone={DEVICE_STATUS[d.status].tone} label={DEVICE_STATUS[d.status].label} />
          </li>
        {/each}
      </ul>
    </section>

    <section class="card" aria-labelledby="hosts-title">
      <h2 id="hosts-title">{t('Freigegebene Dienste')}</h2>
      {#if data.hosts.length}
        <ul class="list">
          {#each data.hosts as h (h)}
            <li><a class="mono" href={`https://${h}`} target="_blank" rel="noopener">{h}</a></li>
          {/each}
        </ul>
      {:else}
        <p class="muted small">{t('Für dich ist noch kein Dienst freigegeben.')}</p>
      {/if}
    </section>
  {/if}
</AppShell>

<style>
  h2 {
    margin: 0;
    font-size: 16px;
  }
  .small {
    font-size: 12px;
    margin: 0;
    line-height: 1.5;
  }
  .block {
    display: block;
  }
  .list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 8px;
  }
  .list li {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
  }
  .list li:last-child {
    border-bottom: 0;
  }
  .grow {
    flex: 1;
    min-width: 0;
  }
</style>

<script lang="ts">
  import { t, tApi } from '../lib/i18n';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import { api, formatDate, ACTION_LABELS, type AuditEntry, type AuditVerify } from '../lib/api';

  const KINDS = ['', 'admin', 'system', 'guest', 'agent'] as const;
  let kind = $state(0);
  let check = $state<AuditVerify | null>(null);

  const PAGE = 100;

  let entries = $state<AuditEntry[]>([]);
  let query = $state('');
  let more = $state(false);
  let error = $state('');
  let open = $state<number | null>(null);

  async function load(append = false) {
    const params = new URLSearchParams({ limit: String(PAGE) });
    if (query.trim()) params.set('q', query.trim());
    if (KINDS[kind]) params.set('kind', KINDS[kind]);
    if (append && entries.length) params.set('before_id', String(entries[entries.length - 1].id));
    try {
      const page = await api.get<AuditEntry[]>(`/audit?${params}`);
      entries = append ? [...entries, ...page] : page;
      more = page.length === PAGE;
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  let timer: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    void query;
    clearTimeout(timer);
    timer = setTimeout(() => load(), 250);
  });

  const detailText = (e: AuditEntry) =>
    [Object.keys(e.details).length ? JSON.stringify(e.details, null, 2) : '', e.hash ? t('Prüfsumme {0}', e.hash) : '']
      .filter(Boolean)
      .join('\n\n');

  async function verify() {
    try {
      check = await api.get<AuditVerify>('/audit/verify');
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  verify();

  function exportCsv() {
    const params = new URLSearchParams();
    if (query.trim()) params.set('q', query.trim());
    if (KINDS[kind]) params.set('kind', KINDS[kind]);
    window.location.href = `/api/audit/export.csv?${params}`;
  }
</script>

<AppShell active="audit">
  <PageHeader
    title={t('Audit-Log')}
    subtitle={t('Jede Änderung und jede Anmeldung – wer, wann, was. Einträge lassen sich nicht ändern oder löschen.')}
    primaryLabel={t('CSV exportieren')}
    primaryIcon="download"
    onPrimary={exportCsv}
  />

  <div class="row">
    <SegmentedControl groupLabel={t('Wer')} options={['Alle', 'Admins', 'System', t('Gäste'), 'Agents']} bind:selected={kind} onChange={() => load()} />
    <label class="search">
      <Icon name="search" size={16} strokeWidth={2} />
      <span class="visually-hidden">{t('Log durchsuchen')}</span>
      <input type="search" placeholder={t('Wer, Aktion oder Ziel …')} bind:value={query} />
    </label>
    {#if check}
      <span class="chain" title={t('Letzte Prüfsumme {0}', check.last_hash)}>
        <StatusPill tone={check.ok ? 'ok' : 'bad'} label={check.ok ? t('Kette intakt · {0} Einträge', check.checked) : t('Kette gebrochen bei #{0}', check.broken_id)} />
      </span>
    {/if}
  </div>
  {#if check && !check.ok}
    <Alert tone="bad" title={t('Das Audit-Log wurde verändert')} text={t('Eintrag #{0} passt nicht zur Prüfsumme seines Vorgängers. Jemand hat die Datenbank direkt bearbeitet – Backup vergleichen.', check.broken_id)} />
  {/if}

  {#if error}<Alert tone="bad" title={t('Fehler')} text={error} />{/if}

  <div class="table-wrap">
    <table class="table">
      <thead>
        <tr>
          <th scope="col">{t('Zeit')}</th>
          <th scope="col">{t('Wer')}</th>
          <th scope="col">{t('Aktion')}</th>
          <th scope="col">{t('Betrifft')}</th>
          <th scope="col">{t('Von')}</th>
        </tr>
      </thead>
      <tbody>
        {#each entries as e (e.id)}
          {@const details = detailText(e)}
          <tr>
            <td class="nowrap muted">{formatDate(e.created_at)}</td>
            <td>{e.actor}</td>
            <td>
              {#if details}
                <button type="button" class="link" aria-expanded={open === e.id} onclick={() => (open = open === e.id ? null : e.id)}>
                  {ACTION_LABELS[e.action] ?? e.action}
                </button>
              {:else}
                {ACTION_LABELS[e.action] ?? e.action}
              {/if}
            </td>
            <td class="mono small">{tApi(e.target) || '–'}</td>
            <td class="mono small muted">{e.ip ?? '–'}</td>
          </tr>
          {#if open === e.id && details}
            <tr class="details"><td colspan="5"><pre class="code">{details}</pre></td></tr>
          {/if}
        {:else}
          <tr><td colspan="5" class="muted">{t('Keine Einträge.')}</td></tr>
        {/each}
      </tbody>
    </table>
  </div>

  {#if more}<div><Button variant="secondary" label={t('Ältere laden')} onClick={() => load(true)} /></div>{/if}

  <p class="muted small">
    {t('Jeder Eintrag trägt die Prüfsumme (SHA-256) seines Vorgängers. Ein geänderter oder gelöschter Eintrag bricht die Kette ab dieser Stelle – die Prüfung oben zeigt, wo.')}
  </p>
</AppShell>

<style>
  .search {
    flex: 1 1 260px;
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    padding: 0 12px;
    max-width: 480px;
    border-radius: var(--radius);
    background: var(--surface);
    border: 1px solid var(--border-input);
    color: var(--text-muted);
  }
  .search input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: transparent;
    color: var(--text);
    font: inherit;
  }
  .nowrap {
    white-space: nowrap;
  }
  .small {
    font-size: 13px;
  }
  .link {
    padding: 0;
    border: none;
    background: none;
    color: var(--accent-text);
    font: inherit;
    cursor: pointer;
    text-align: left;
  }
  .details td {
    border-top: none;
    padding-top: 0;
  }
  p.small {
    margin: 0;
  }
</style>

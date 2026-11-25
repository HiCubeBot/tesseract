<script lang="ts">
  import { t } from '../lib/i18n';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import CustomCerts from '../lib/components/CustomCerts.svelte';
  import { api, formatAgo, formatDay, type CertificateOverview } from '../lib/api';

  let data = $state<CertificateOverview | null>(null);
  let loading = $state(false);
  let error = $state('');
  let filter = $state(0);
  let query = $state('');
  let open = $state<string | null>(null);

  async function load(refresh = false) {
    loading = true;
    try {
      data = await api.get<CertificateOverview>(`/certificates${refresh ? '?refresh=true' : ''}`);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }
  load();

  const STATUS = {
    ok: { tone: 'ok', label: t('gültig') },
    soon: { tone: 'warn', label: t('läuft bald ab') },
    expired: { tone: 'bad', label: t('abgelaufen') }
  } as const;
  const SOURCE: Record<string, string> = {
    'http-01': 'HTTP-01',
    'dns-01': 'DNS-01',
    wildcard: t('Wildcard (DNS-01)'),
    lokal: t('Caddy-CA'),
    eigenes: 'hochgeladen',
    unbekannt: '–'
  };

  const visible = $derived(
    (data?.certificates ?? []).filter((c) => {
      if (filter === 1 && c.status === 'ok') return false;
      if (filter === 2 && c.source !== 'wildcard') return false;
      const q = query.trim().toLowerCase();
      return !q || [...c.names, ...c.hosts, c.issuer].some((s) => s.toLowerCase().includes(q));
    })
  );
  const counts = $derived({
    all: data?.certificates.length ?? 0,
    attention: data?.certificates.filter((c) => c.status !== 'ok').length ?? 0,
    wild: data?.certificates.filter((c) => c.source === 'wildcard').length ?? 0
  });
</script>

<AppShell active="certificates">
  <PageHeader
    title={t('Zertifikate')}
    subtitle={data ? t('Stand {0} · direkt bei Caddy ausgelesen', formatAgo(data.checked_at)) : t('Alle Zertifikate, die Caddy ausliefert.')}
    primaryLabel={loading ? t('Prüft …') : t('Neu prüfen')}
    primaryIcon="refresh"
    onPrimary={() => !loading && load(true)}
  />

  {#if error}<Alert tone="bad" title={t('Fehler')} text={error} />{/if}

  {#if data?.errors.length}
    <Alert
      tone="warn"
      title={t('{0} Name(n) ohne Zertifikat', data.errors.length)}
      text={data.errors.map((e) => `${e.name}: ${e.error}`).join(' · ')}
    />
  {/if}

  <div class="row">
    <SegmentedControl
      groupLabel={t('Filter')}
      options={[t('Alle · {0}', counts.all), t('Achtung · {0}', counts.attention), t('Wildcard · {0}', counts.wild)]}
      bind:selected={filter}
    />
    <label class="search">
      <Icon name="search" size={16} strokeWidth={2} />
      <span class="visually-hidden">{t('Zertifikate durchsuchen')}</span>
      <input type="search" placeholder={t('Name, Host oder Aussteller')} bind:value={query} />
    </label>
  </div>

  {#if data && data.certificates.length === 0}
    <EmptyState icon="hosts" title={t('Noch keine Zertifikate')} text={t('Sobald Hosts angelegt sind, erscheinen ihre Zertifikate hier.')} />
  {:else if data}
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th scope="col">{t('Name')}</th>
            <th scope="col">{t('Aussteller')}</th>
            <th scope="col">{t('Prüfung')}</th>
            <th scope="col">{t('Gültig bis')}</th>
            <th scope="col">{t('Hosts')}</th>
            <th scope="col">{t('Status')}</th>
          </tr>
        </thead>
        <tbody>
          {#each visible as c (c.fingerprint)}
            {@const st = STATUS[c.status]}
            <tr>
              <td>
                <button type="button" class="link mono" aria-expanded={open === c.fingerprint} onclick={() => (open = open === c.fingerprint ? null : c.fingerprint)}>
                  {c.names[0] ?? '–'}{c.names.length > 1 ? ` +${c.names.length - 1}` : ''}
                </button>
              </td>
              <td>{c.issuer}</td>
              <td class="muted">{SOURCE[c.source]}</td>
              <td class="nowrap">{formatDay(c.not_after)} <span class="muted small">{t('· {0} Tage', c.days_left)}</span></td>
              <td class="small">{c.hosts.length} {c.hosts.length === 1 ? t('Host') : t('Hosts')}</td>
              <td><StatusPill tone={st.tone} label={st.label} /></td>
            </tr>
            {#if open === c.fingerprint}
              <tr class="details">
                <td colspan="6">
                  <dl>
                    <dt>{t('Namen im Zertifikat')}</dt><dd class="mono">{c.names.join(', ')}</dd>
                    <dt>{t('Genutzt von')}</dt>
                    <dd class="mono">{c.hosts.join(', ') || t('– (nur vorgehalten)')}</dd>
                    <dt>{t('Aussteller')}</dt><dd>{c.issuer_raw}</dd>
                    <dt>{t('Gültig')}</dt><dd>{formatDay(c.not_before)} – {formatDay(c.not_after)}</dd>
                    <dt>{t('Node')}</dt><dd>{c.node}</dd>
                    <dt>{t('Fingerabdruck')}</dt><dd class="mono fp">{c.fingerprint}</dd>
                  </dl>
                </td>
              </tr>
            {/if}
          {:else}
            <tr><td colspan="6" class="muted">{t('Keine Treffer.')}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="muted small">
      {t('Caddy erneuert Let\'s-Encrypt-Zertifikate automatisch rund 30 Tage vor Ablauf. „Läuft bald ab“ (unter 21 Tagen) heißt meist: die Erneuerung klappt nicht – Port 80, DNS oder Cloudflare-Token prüfen.')}
    </p>
  {/if}

  <CustomCerts onChange={() => load(true)} />
</AppShell>

<style>
  .search {
    flex: 1 1 240px;
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    padding: 0 12px;
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
  .link {
    padding: 0;
    border: none;
    background: none;
    color: var(--text);
    font-weight: 500;
    cursor: pointer;
    text-align: left;
  }
  .link:hover {
    text-decoration: underline;
  }
  .nowrap {
    white-space: nowrap;
  }
  .small {
    font-size: 12px;
  }
  p.small {
    margin: 0;
    line-height: 1.5;
  }
  .details td {
    border-top: none;
    background: var(--bg);
  }
  dl {
    margin: 0;
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 6px 16px;
    font-size: 13px;
  }
  dt {
    color: var(--text-muted);
  }
  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
  .fp {
    font-size: 11px;
  }
</style>

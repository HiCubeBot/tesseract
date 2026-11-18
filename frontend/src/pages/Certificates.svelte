<script lang="ts">
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
    ok: { tone: 'ok', label: 'gültig' },
    soon: { tone: 'warn', label: 'läuft bald ab' },
    expired: { tone: 'bad', label: 'abgelaufen' }
  } as const;
  const SOURCE: Record<string, string> = {
    'http-01': 'HTTP-01',
    'dns-01': 'DNS-01',
    wildcard: 'Wildcard (DNS-01)',
    lokal: 'Caddy-CA',
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
    title="Zertifikate"
    subtitle={data ? `Stand ${formatAgo(data.checked_at)} · direkt bei Caddy ausgelesen` : 'Alle Zertifikate, die Caddy ausliefert.'}
    primaryLabel={loading ? 'Prüft …' : 'Neu prüfen'}
    primaryIcon="refresh"
    onPrimary={() => !loading && load(true)}
  />

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if data?.errors.length}
    <Alert
      tone="warn"
      title={`${data.errors.length} Name(n) ohne Zertifikat`}
      text={data.errors.map((e) => `${e.name}: ${e.error}`).join(' · ')}
    />
  {/if}

  <div class="row">
    <SegmentedControl
      groupLabel="Filter"
      options={[`Alle · ${counts.all}`, `Achtung · ${counts.attention}`, `Wildcard · ${counts.wild}`]}
      bind:selected={filter}
    />
    <label class="search">
      <Icon name="search" size={16} strokeWidth={2} />
      <span class="visually-hidden">Zertifikate durchsuchen</span>
      <input type="search" placeholder="Name, Host oder Aussteller" bind:value={query} />
    </label>
  </div>

  {#if data && data.certificates.length === 0}
    <EmptyState icon="hosts" title="Noch keine Zertifikate" text="Sobald Hosts angelegt sind, erscheinen ihre Zertifikate hier." />
  {:else if data}
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Aussteller</th>
            <th scope="col">Prüfung</th>
            <th scope="col">Gültig bis</th>
            <th scope="col">Hosts</th>
            <th scope="col">Status</th>
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
              <td class="nowrap">{formatDay(c.not_after)} <span class="muted small">· {c.days_left} Tage</span></td>
              <td class="small">{c.hosts.length} {c.hosts.length === 1 ? 'Host' : 'Hosts'}</td>
              <td><StatusPill tone={st.tone} label={st.label} /></td>
            </tr>
            {#if open === c.fingerprint}
              <tr class="details">
                <td colspan="6">
                  <dl>
                    <dt>Namen im Zertifikat</dt><dd class="mono">{c.names.join(', ')}</dd>
                    <dt>Genutzt von</dt>
                    <dd class="mono">{c.hosts.join(', ') || '– (nur vorgehalten)'}</dd>
                    <dt>Aussteller</dt><dd>{c.issuer_raw}</dd>
                    <dt>Gültig</dt><dd>{formatDay(c.not_before)} – {formatDay(c.not_after)}</dd>
                    <dt>Node</dt><dd>{c.node}</dd>
                    <dt>Fingerabdruck</dt><dd class="mono fp">{c.fingerprint}</dd>
                  </dl>
                </td>
              </tr>
            {/if}
          {:else}
            <tr><td colspan="6" class="muted">Keine Treffer.</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="muted small">
      Caddy erneuert Let's-Encrypt-Zertifikate automatisch rund 30 Tage vor Ablauf. „Läuft bald ab“ (unter 21 Tagen) heißt meist:
      die Erneuerung klappt nicht – Port 80, DNS oder Cloudflare-Token prüfen.
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

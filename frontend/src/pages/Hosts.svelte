<script lang="ts">
  import { locale, t } from '../lib/i18n';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import { session } from '../lib/session.svelte';
  import { hostHref } from '../lib/permissions';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import Switch from '../lib/components/Switch.svelte';
  import Sparkline from '../lib/components/Sparkline.svelte';
  import { api, type Host, type NodeInfo } from '../lib/api';
  import { accessLabel, hostStatus, protectionLabel, setEnabled, upstreamLabel } from '../lib/hosts';

  let hosts = $state<Host[]>([]);
  let nodes = $state<NodeInfo[]>([]);
  let loaded = $state(false);
  let loadError = $state('');
  let filter = $state(0);
  let query = $state('');
  let nodeFilter = $state(0);
  let toggling = $state<number | null>(null);

  async function load() {
    try {
      [hosts, nodes] = await Promise.all([api.get<Host[]>('/hosts'), api.get<NodeInfo[]>('/nodes')]);
      loadError = '';
    } catch (e) {
      loadError = e instanceof Error ? e.message : String(e);
    } finally {
      loaded = true;
    }
  }
  load();

  // Anfragen der letzten 24 Stunden je Domain (stündlich) – Fehler bleiben still
  let activity = $state<Record<string, { total: number; hourly: number[] }>>({});
  api
    .get<{ hosts: Record<string, { total: number; hourly: number[] }> }>('/stats/activity')
    .then((r) => (activity = r.hosts))
    .catch(() => {});

  async function toggle(h: Host, enabled: boolean) {
    toggling = h.id;
    const updated = await setEnabled(h, enabled);
    if (updated) hosts = hosts.map((x) => (x.id === updated.id ? updated : x));
    toggling = null;
  }

  const counts = $derived({
    all: hosts.length,
    live: hosts.filter((h) => !h.draft && h.enabled).length,
    off: hosts.filter((h) => !h.draft && !h.enabled).length,
    draft: hosts.filter((h) => h.draft).length,
    mtls: hosts.filter((h) => h.access === 'mtls').length
  });

  const visible = $derived(
    hosts.filter((h) => {
      if (filter === 1 && (h.draft || !h.enabled)) return false;
      if (filter === 2 && h.access !== 'mtls') return false;
      if (filter === 3 && (h.draft || h.enabled)) return false;
      if (filter === 4 && !h.draft) return false;
      if (nodeFilter && h.node.id !== nodeFilter) return false;
      const q = query.trim().toLowerCase();
      return !q || h.domain.includes(q) || upstreamLabel(h).includes(q);
    })
  );
</script>

<AppShell active="hosts">
  <PageHeader
    title={t('Proxy-Hosts')}
    subtitle={t('Öffentlich mit Let\'s Encrypt – oder nur für freigegebene Geräte (mTLS).')}
    primaryLabel={session.isAdmin ? t('Host anlegen') : undefined}
    primaryHref={session.isAdmin ? '#/hosts/new' : undefined}
  />

  {#if loadError}<Alert tone="bad" title={t('Hosts konnten nicht geladen werden')} text={loadError} />{/if}

  <div class="row">
    <SegmentedControl
      groupLabel={t('Status filtern')}
      options={[
        t('Alle · {0}', counts.all),
        t('Aktiv · {0}', counts.live),
        t('mTLS · {0}', counts.mtls),
        t('Deaktiviert · {0}', counts.off),
        t('Entwürfe · {0}', counts.draft)
      ]}
      bind:selected={filter}
    />
    <label class="search">
      <Icon name="search" size={16} strokeWidth={2} />
      <span class="visually-hidden">{t('Hosts durchsuchen')}</span>
      <input type="search" placeholder={t('Domain oder Ziel suchen')} bind:value={query} />
    </label>
    {#if nodes.length > 1}
      <label class="field inline">
        {t('Node')}
        <select class="input" bind:value={nodeFilter}>
          <option value={0}>{t('Alle Nodes')}</option>
          {#each nodes as n (n.id)}<option value={n.id}>{n.name}</option>{/each}
        </select>
      </label>
    {/if}
  </div>

  <section aria-label={t('Host-Liste')}>
    {#if loaded && hosts.length === 0}
      <EmptyState
        icon="hosts"
        title={t('Noch keine Hosts')}
        text={t('Lege den ersten Proxy-Host an – Caddy holt das Zertifikat automatisch.')}
        actionLabel={session.isAdmin ? t('Host anlegen') : undefined}
        actionHref={session.isAdmin ? '#/hosts/new' : undefined}
      />
    {:else}
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th scope="col">{t('Domain')}</th>
              <th scope="col">{t('Ziel')}</th>
              <th scope="col">{t('Node')}</th>
              <th scope="col">{t('Zugriff')}</th>
              <th scope="col">{t('Schutz')}</th>
              <th scope="col" class="num">{t('Anfragen · 24 h')}</th>
              <th scope="col">{t('Status')}</th>
              <th scope="col"><span class="visually-hidden">{t('Aktiv')}</span></th>
            </tr>
          </thead>
          <tbody>
            {#each visible as h (h.id)}
              {@const st = hostStatus(h)}
              <tr class:off={!h.draft && !h.enabled}>
                <td>
                  <a class="mono domain" href={hostHref(session.role, h.id)}>{h.domain}</a>
                  {#if h.source === 'docker'}<span class="src" title={t('aus den Docker-Labels von {0}', h.source_ref?.split(':').slice(1).join(':'))}>{t('Docker')}</span>{/if}
                </td>
                <td class="mono muted small">{upstreamLabel(h)}</td>
                <td class="muted">{h.node.name}</td>
                <td>
                  {#if h.internal}
                    <span class="access internal"><Icon name="server" size={13} strokeWidth={2.2} />{t('Intern{0}', h.access === 'mtls' ? t(' + mTLS') : '')}</span>
                  {:else if h.access === 'mtls'}
                    <span class="access mtls"><Icon name="lock" size={13} strokeWidth={2.2} />{t('mTLS')}</span>
                  {:else}
                    <span class="access"><Icon name="globe" size={13} strokeWidth={2.2} />{t('Öffentlich')}</span>
                  {/if}
                  <span class="muted tiny block">{accessLabel(h)}</span>
                </td>
                <td class="small nowrap">
                  {#if session.isAdmin}
                    <a class="plain" href={`#/hosts/${h.id}/security`}>{protectionLabel(h)}</a>
                  {:else}
                    {protectionLabel(h)}
                  {/if}
                </td>
                <td class="activity">
                  {#if activity[h.domain]}
                    {@const a = activity[h.domain]}
                    <a class="plain act" href={`#/hosts/${h.id}/stats`} title={t('Statistik öffnen')}>
                      <span class="num-val">{a.total.toLocaleString(locale)}</span>
                      <Sparkline values={a.hourly} label={t('Anfragen der letzten 24 Stunden: {0}', a.total)} />
                    </a>
                  {:else}
                    <span class="muted num-val">0</span>
                  {/if}
                </td>
                <td><StatusPill tone={st.tone} label={st.label} /></td>
                <td class="switch-cell">
                  {#if !h.draft && session.isAdmin}
                    <Switch
                      checked={h.enabled}
                      disabled={toggling !== null}
                      label={h.enabled ? `${h.domain} deaktivieren` : `${h.domain} aktivieren`}
                      onChange={(on) => toggle(h, on)}
                    />
                  {/if}
                </td>
              </tr>
            {:else}
              <tr><td colspan="8" class="muted">{t('Keine Treffer.')}</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>
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
  .inline {
    flex-direction: row;
    align-items: center;
    gap: 8px;
  }
  .domain {
    color: var(--text);
    font-weight: 500;
    text-decoration: none;
  }
  .src {
    margin-left: 8px;
    padding: 2px 7px;
    border-radius: var(--radius-pill);
    background: var(--surface-raised);
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 600;
    vertical-align: middle;
  }
  .domain:hover {
    text-decoration: underline;
  }
  tr.off td:not(.switch-cell) {
    opacity: 0.55;
  }
  .switch-cell {
    width: 1%;
    text-align: right;
  }
  .small {
    font-size: 13px;
  }
  .tiny {
    font-size: 11px;
  }
  .nowrap {
    white-space: nowrap;
  }
  .plain {
    color: var(--text-soft);
    text-decoration: none;
  }
  .plain:hover {
    text-decoration: underline;
  }
  .block {
    display: block;
    margin-top: 4px;
  }
  .access.internal {
    color: var(--warn-text);
    background: var(--warn-soft);
  }
  .access.mtls {
    color: var(--accent-text);
    background: rgba(139, 124, 246, 0.16);
  }
  .access {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: var(--radius-pill);
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
    color: var(--ok-text);
    background: var(--ok-soft);
  }
  th.num {
    text-align: right;
  }
  .activity {
    text-align: right;
  }
  .act {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    text-decoration: none;
  }
  .num-val {
    font-variant-numeric: tabular-nums;
    min-width: 48px;
    text-align: right;
  }
</style>

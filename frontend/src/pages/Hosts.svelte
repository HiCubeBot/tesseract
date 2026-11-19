<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import Switch from '../lib/components/Switch.svelte';
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
    title="Proxy-Hosts"
    subtitle="Öffentlich mit Let's Encrypt – oder nur für freigegebene Geräte (mTLS)."
    primaryLabel="Host anlegen"
    primaryHref="#/hosts/new"
  />

  {#if loadError}<Alert tone="bad" title="Hosts konnten nicht geladen werden" text={loadError} />{/if}

  <div class="row">
    <SegmentedControl
      groupLabel="Status filtern"
      options={[
        `Alle · ${counts.all}`,
        `Aktiv · ${counts.live}`,
        `mTLS · ${counts.mtls}`,
        `Deaktiviert · ${counts.off}`,
        `Entwürfe · ${counts.draft}`
      ]}
      bind:selected={filter}
    />
    <label class="search">
      <Icon name="search" size={16} strokeWidth={2} />
      <span class="visually-hidden">Hosts durchsuchen</span>
      <input type="search" placeholder="Domain oder Ziel suchen" bind:value={query} />
    </label>
    {#if nodes.length > 1}
      <label class="field inline">
        Node
        <select class="input" bind:value={nodeFilter}>
          <option value={0}>Alle Nodes</option>
          {#each nodes as n (n.id)}<option value={n.id}>{n.name}</option>{/each}
        </select>
      </label>
    {/if}
  </div>

  <section aria-label="Host-Liste">
    {#if loaded && hosts.length === 0}
      <EmptyState
        icon="hosts"
        title="Noch keine Hosts"
        text="Lege den ersten Proxy-Host an – Caddy holt das Zertifikat automatisch."
        actionLabel="Host anlegen"
        actionHref="#/hosts/new"
      />
    {:else}
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th scope="col">Domain</th>
              <th scope="col">Ziel</th>
              <th scope="col">Node</th>
              <th scope="col">Zugriff</th>
              <th scope="col">Schutz</th>
              <th scope="col">Status</th>
              <th scope="col"><span class="visually-hidden">Aktiv</span></th>
            </tr>
          </thead>
          <tbody>
            {#each visible as h (h.id)}
              {@const st = hostStatus(h)}
              <tr class:off={!h.draft && !h.enabled}>
                <td><a class="mono domain" href={`#/hosts/${h.id}`}>{h.domain}</a></td>
                <td class="mono muted small">{upstreamLabel(h)}</td>
                <td class="muted">{h.node.name}</td>
                <td>
                  {#if h.internal}
                    <span class="access internal"><Icon name="server" size={13} strokeWidth={2.2} />Intern{h.access === 'mtls' ? ' + mTLS' : ''}</span>
                  {:else if h.access === 'mtls'}
                    <span class="access mtls"><Icon name="lock" size={13} strokeWidth={2.2} />mTLS</span>
                  {:else}
                    <span class="access"><Icon name="globe" size={13} strokeWidth={2.2} />Öffentlich</span>
                  {/if}
                  <span class="muted tiny block">{accessLabel(h)}</span>
                </td>
                <td class="small nowrap">
                  <a class="plain" href={`#/hosts/${h.id}/security`}>{protectionLabel(h)}</a>
                </td>
                <td><StatusPill tone={st.tone} label={st.label} /></td>
                <td class="switch-cell">
                  {#if !h.draft}
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
              <tr><td colspan="7" class="muted">Keine Treffer.</td></tr>
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
</style>

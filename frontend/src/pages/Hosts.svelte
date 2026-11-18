<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import HostForm from '../lib/components/HostForm.svelte';
  import AccessForm from '../lib/components/AccessForm.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import {
    api,
    formatDate,
    type CAStatus,
    type Group,
    type Host,
    type HostInput,
    type HostSaved,
    type NodeInfo,
    type Person
  } from '../lib/api';
  import { accessLabel, hostStatus, protectionLabel, toInput, upstreamLabel } from '../lib/hosts';
  import { reportApply } from '../lib/nodes';
  import { router } from '../lib/router.svelte';
  import { toasts } from '../lib/toast.svelte';

  let { params = {} }: { params?: Record<string, string> } = $props();

  let hosts = $state<Host[]>([]);
  let nodes = $state<NodeInfo[]>([]);
  let groups = $state<Group[]>([]);
  let persons = $state<Person[]>([]);
  let caConfigured = $state(false);
  let loaded = $state(false);
  let loadError = $state('');
  let filter = $state(0);
  let query = $state('');
  let nodeFilter = $state(0);

  let edit = $state<HostInput | null>(null);
  let saving = $state(false);
  let saveError = $state('');
  let confirmDelete = $state(false);

  const selectedId = $derived(params.id ? Number(params.id) : null);
  const selected = $derived(hosts.find((h) => h.id === selectedId) ?? null);

  async function load() {
    try {
      let ca: CAStatus;
      [hosts, nodes, groups, persons, ca] = await Promise.all([
        api.get<Host[]>('/hosts'),
        api.get<NodeInfo[]>('/nodes'),
        api.get<Group[]>('/groups'),
        api.get<Person[]>('/persons'),
        api.get<CAStatus>('/ca')
      ]);
      caConfigured = ca.configured;
      loadError = '';
    } catch (e) {
      loadError = e instanceof Error ? e.message : String(e);
    } finally {
      loaded = true;
    }
  }
  load();

  // Bearbeiten-Panel mit dem gewählten Host füllen
  $effect(() => {
    edit = selected ? toInput(selected) : null;
    saveError = '';
    confirmDelete = false;
  });

  const counts = $derived({
    all: hosts.length,
    live: hosts.filter((h) => !h.draft && h.enabled).length,
    draft: hosts.filter((h) => h.draft).length,
    mtls: hosts.filter((h) => h.access === 'mtls').length
  });

  const visible = $derived(
    hosts.filter((h) => {
      if (filter === 1 && (h.draft || !h.enabled)) return false;
      if (filter === 2 && h.access !== 'mtls') return false;
      if (filter === 3 && !h.draft) return false;
      if (nodeFilter && h.node.id !== nodeFilter) return false;
      const q = query.trim().toLowerCase();
      return !q || h.domain.includes(q) || upstreamLabel(h).includes(q);
    })
  );

  async function save(activate = false) {
    if (!edit || !selected) return;
    saving = true;
    saveError = '';
    try {
      const body = { ...edit, draft: activate ? false : edit.draft, upstream_port: Number(edit.upstream_port) };
      const r = await api.put<HostSaved>(`/hosts/${selected.id}`, body);
      reportApply(r.apply, r.host.domain);
      await load();
    } catch (e) {
      saveError = e instanceof Error ? e.message : String(e);
    } finally {
      saving = false;
    }
  }

  async function remove() {
    if (!selected) return;
    const domain = selected.domain;
    try {
      const r = await api.del<{ ok: boolean; error: string | null }>(`/hosts/${selected.id}`);
      if (r.ok) toasts.show('ok', `${domain} gelöscht und übertragen.`);
      else toasts.show('warn', `${domain} gelöscht, aber nicht übertragen: ${r.error}`, 12000);
      router.go('hosts');
      await load();
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    } finally {
      confirmDelete = false;
    }
  }
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
      options={[`Alle · ${counts.all}`, `Aktiv · ${counts.live}`, `mTLS · ${counts.mtls}`, `Entwürfe · ${counts.draft}`]}
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

  <div class="layout">
    <section class="list" aria-label="Host-Liste">
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
              </tr>
            </thead>
            <tbody>
              {#each visible as h (h.id)}
                {@const st = hostStatus(h)}
                <tr class:selected={h.id === selectedId}>
                  <td><a class="mono domain" href={`#/hosts/${h.id}`}>{h.domain}</a></td>
                  <td class="mono muted small">{upstreamLabel(h)}</td>
                  <td class="muted">{h.node.name}</td>
                  <td>
                    {#if h.access === 'mtls'}
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
                </tr>
              {:else}
                <tr><td colspan="6" class="muted">Keine Treffer.</td></tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </section>

    {#if selected && edit}
      <section class="card panel" aria-labelledby="edit-title">
        <div class="panel-head">
          <div class="stack">
            <span class="eyebrow">Host bearbeiten · Version {selected.version}</span>
            <h2 id="edit-title" class="mono">{selected.domain}</h2>
          </div>
          <a href="#/hosts" class="close" aria-label="Schließen"><Icon name="close" size={16} /></a>
        </div>

        {#if selected.draft}
          <Alert tone="warn" title="Entwurf" text="Dieser Host ist gespeichert, aber noch nicht an Caddy übertragen." />
        {/if}

        <HostForm bind:value={edit} {nodes} compact />
        <div class="divider"></div>
        <AccessForm bind:value={edit} {groups} {persons} {caConfigured} compact />

        <span class="muted small">Zuletzt geändert {formatDate(selected.updated_at)}</span>

        {#if saveError}<p class="field-error" role="alert">{saveError}</p>{/if}

        <div class="row">
          {#if selected.draft}
            <Button label={saving ? 'Überträgt …' : 'Anlegen & übertragen'} disabled={saving} onClick={() => save(true)} />
            <Button variant="secondary" label="Entwurf speichern" disabled={saving} onClick={() => save(false)} />
          {:else}
            <Button label={saving ? 'Überträgt …' : 'Speichern & übertragen'} disabled={saving} onClick={() => save(false)} />
          {/if}
          <Button variant="secondary" label="Verlauf" href={`#/hosts/${selected.id}/history`} />
          <Button variant="secondary" label="Sicherheit" href={`#/hosts/${selected.id}/security`} />
          <span class="spacer"></span>
          <Button variant="danger" icon="trash" label="Löschen" onClick={() => (confirmDelete = true)} />
        </div>

        {#if confirmDelete}
          <ConfirmDialog
            title="Host löschen?"
            text={`${selected.domain} wird aus Caddy entfernt. Der Verlauf geht verloren.`}
            word={selected.domain}
            confirmLabel="Endgültig löschen"
            onConfirm={remove}
            onCancel={() => (confirmDelete = false)}
          />
        {/if}
      </section>
    {/if}
  </div>
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
  .layout {
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    align-items: flex-start;
  }
  .list {
    flex: 999 1 560px;
    min-width: 0;
  }
  .panel {
    flex: 1 1 380px;
    border-color: #3a3460;
  }
  .panel-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
  }
  .panel-head h2 {
    margin: 0;
    font-size: 17px;
    overflow-wrap: anywhere;
  }
  .stack {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .close {
    width: 36px;
    height: 36px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius);
    color: var(--text-muted);
  }
  .domain {
    color: var(--text);
    font-weight: 500;
    text-decoration: none;
  }
  .domain:hover {
    text-decoration: underline;
  }
  tr.selected td {
    background: rgba(139, 124, 246, 0.08);
  }
  tr.selected td:first-child {
    box-shadow: inset 3px 0 0 var(--accent);
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
  .divider {
    border-top: 1px solid var(--border);
  }
  .access.mtls {
    color: #c9c1ff;
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

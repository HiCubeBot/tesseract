<script lang="ts">
  // Kopf der Host-Seiten: Domain, Status, Aktiv-Schalter und Tabs
  // (Allgemein · Zugriff · Sicherheit · Statistik · Verlauf)
  import StatusPill from './StatusPill.svelte';
  import Switch from './Switch.svelte';
  import type { Host } from '../api';
  import { hostStatus, setEnabled, type HostTab } from '../hosts';
  import { session } from '../session.svelte';

  interface Props {
    hostId: number;
    host: Host | null;
    tab: HostTab;
    /** ungespeicherte Änderungen – Tab-Wechsel fragt dann nach */
    dirty?: boolean;
    /** nach dem Ein-/Ausschalten: der aktualisierte Host */
    onChange?: (host: Host) => void;
  }

  let { hostId, host, tab, dirty = false, onChange }: Props = $props();
  let busy = $state(false);

  const allTabs: { id: HostTab; label: string; path: string }[] = [
    { id: 'general', label: 'Allgemein', path: '' },
    { id: 'access', label: 'Zugriff', path: '/access' },
    { id: 'security', label: 'Sicherheit', path: '/security' },
    { id: 'stats', label: 'Statistik', path: '/stats' },
    { id: 'history', label: 'Verlauf', path: '/history' }
  ];
  // Personen per Zertifikat (Lesen, Eigene Dienste): nur Statistik und Verlauf
  const tabs = $derived(session.isAdmin ? allTabs : allTabs.filter((t) => t.id === 'stats' || t.id === 'history'));

  function leave(e: MouseEvent) {
    if (dirty && !confirm('Es gibt ungespeicherte Änderungen. Trotzdem wechseln und verwerfen?')) e.preventDefault();
  }

  async function toggle(enabled: boolean) {
    if (!host) return;
    busy = true;
    try {
      const updated = await setEnabled(host, enabled);
      if (updated) onChange?.(updated);
    } finally {
      busy = false;
    }
  }

  const st = $derived(host ? hostStatus(host) : null);
</script>

<header class="head">
  <a href="#/hosts" class="crumb" onclick={leave}>← Proxy-Hosts</a>
  <div class="title-row">
    <h1 class="mono">{host?.domain ?? '…'}</h1>
    {#if st}<StatusPill tone={st.tone} label={st.label} />{/if}
    <span class="spacer"></span>
    {#if host && !host.draft && session.isAdmin}
      <span class="enabled">
        <span class="muted small">{host.enabled ? 'Aktiv' : 'Deaktiviert'}</span>
        <Switch
          checked={host.enabled}
          disabled={busy}
          label={host.enabled ? `${host.domain} deaktivieren` : `${host.domain} aktivieren`}
          onChange={toggle}
        />
      </span>
    {/if}
  </div>
  {#if host}
    <span class="muted small">
      {host.node.name} · Version {host.version}{host.enabled || host.draft ? '' : ' · deaktiviert, wird nicht an Caddy übertragen'}
    </span>
  {/if}
  <nav class="tabs" aria-label="Bereiche des Hosts">
    {#each tabs as t (t.id)}
      <a
        href={`#/hosts/${hostId}${t.path}`}
        class:on={t.id === tab}
        aria-current={t.id === tab ? 'page' : undefined}
        onclick={t.id === tab ? undefined : leave}>{t.label}</a
      >
    {/each}
  </nav>
</header>

<style>
  .head {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .crumb {
    font-size: 13px;
    font-weight: 500;
    text-decoration: none;
  }
  .title-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px 14px;
  }
  h1 {
    margin: 0;
    font-size: 24px;
    letter-spacing: -0.02em;
    overflow-wrap: anywhere;
  }
  .spacer {
    flex: 1;
  }
  .enabled {
    display: inline-flex;
    align-items: center;
    gap: 10px;
  }
  .muted {
    color: var(--text-muted);
  }
  .small {
    font-size: 13px;
  }
  .tabs {
    display: flex;
    gap: 4px;
    margin-top: 10px;
    border-bottom: 1px solid var(--border);
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
  }
  .tabs a {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    padding: 0 14px;
    border-bottom: 2px solid transparent;
    color: var(--text-muted);
    font-size: 14px;
    font-weight: 500;
    text-decoration: none;
    white-space: nowrap;
  }
  .tabs a:hover {
    color: var(--text);
  }
  .tabs a.on {
    color: var(--text);
    border-bottom-color: var(--accent);
  }
</style>

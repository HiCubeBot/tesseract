<script lang="ts">
  import Icon from './Icon.svelte';
  import { icons } from '../icons';
  import { session } from '../session.svelte';

  type NavId =
    | 'main'
    | 'hosts'
    | 'certificates'
    | 'users'
    | 'devices'
    | 'access'
    | 'nodes'
    | 'stats'
    | 'audit'
    | 'settings';

  interface Props {
    active?: NavId;
  }

  let { active = 'main' }: Props = $props();

  const nav: { id: NavId; label: string; href: string; count?: string; d: string }[] = [
    { id: 'main', label: 'Übersicht', href: '#/', d: icons.grid },
    { id: 'hosts', label: 'Proxy-Hosts', href: '#/hosts', d: icons.globe },
    { id: 'certificates', label: 'Zertifikate', href: '#/certificates', d: icons.okCircle },
    { id: 'users', label: 'Nutzer', href: '#/users', d: icons.users },
    { id: 'devices', label: 'Geräte', href: '#/devices', d: icons.device },
    { id: 'access', label: 'Zugriff', href: '#/access', d: icons.lock },
    { id: 'nodes', label: 'Nodes', href: '#/nodes', d: icons.server },
    { id: 'stats', label: 'Statistik', href: '#/stats', d: icons.chart },
    { id: 'audit', label: 'Audit-Log', href: '#/audit', d: icons.clipboard },
    { id: 'settings', label: 'Einstellungen', href: '#/settings', d: icons.sliders }
  ];
</script>

<nav aria-label="Hauptnavigation" class="sidebar">
  <div class="brand">
    <div class="logo">
      <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0E1014" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h18v18H3z"></path><path d="M8 8h8v8H8z"></path><path d="M3 3l5 5M21 3l-5 5M3 21l5-5M21 21l-5-5"></path></svg>
    </div>
    <div class="stack">
      <span class="brand-name">Tesseract</span>
      <span class="muted small">Caddy-Verwaltung</span>
    </div>
  </div>

  <div class="items">
    {#each nav as item (item.id)}
      <a href={item.href} class="item" class:current={item.id === active} aria-current={item.id === active ? 'page' : undefined}>
        <Icon d={item.d} />
        <span class="label">{item.label}</span>
        {#if item.count}<span class="count">{item.count}</span>{/if}
      </a>
    {/each}
  </div>

  <div class="brand user">
    <div class="avatar">{(session.user?.username ?? '?').slice(0, 2).toUpperCase()}</div>
    <div class="stack grow">
      <span class="user-name">{session.user?.username ?? 'nicht angemeldet'}</span>
      <span class="muted small">Controller</span>
    </div>
    {#if session.user}
      <button type="button" class="logout" onclick={() => session.logout()} aria-label="Abmelden" title="Abmelden">
        <Icon d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10" />
      </button>
    {/if}
  </div>
</nav>

<style>
  .sidebar {
    width: 100%;
    padding: 18px 14px;
    display: flex;
    flex-direction: column;
    gap: 22px;
    font-family: var(--font-sans);
    color: var(--text);
    background: var(--sidebar);
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 8px;
  }
  .logo {
    width: 34px;
    height: 34px;
    border-radius: 9px;
    background: var(--text);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .stack {
    display: flex;
    flex-direction: column;
  }
  .brand-name {
    font-weight: 700;
    font-size: 15px;
    letter-spacing: -0.01em;
  }
  .muted {
    color: var(--text-muted);
  }
  .small {
    font-size: 12px;
  }
  .items {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 10px;
    min-height: 44px;
    border-radius: var(--radius);
    text-decoration: none;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-muted);
    background: transparent;
  }
  .item:hover {
    color: var(--text);
    background: #1a1e26;
  }
  .item.current {
    color: var(--text);
    background: var(--surface-raised);
  }
  .label {
    flex-grow: 1;
  }
  .count {
    font-size: 12px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }
  .grow {
    flex-grow: 1;
    min-width: 0;
  }
  .logout {
    width: 36px;
    height: 36px;
    border-radius: var(--radius);
    border: 1px solid var(--border-input);
    background: transparent;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }
  .logout:hover {
    color: var(--text);
  }
  .avatar {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: var(--surface-active);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 600;
  }
  .user-name {
    font-size: 13px;
    font-weight: 500;
  }
</style>

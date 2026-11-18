<script lang="ts">
  import Icon from './Icon.svelte';
  import { icons } from '../icons';

  type NavId = 'main' | 'hosts' | 'users' | 'devices' | 'access' | 'nodes' | 'stats' | 'audit' | 'settings';

  interface Props {
    active?: NavId;
  }

  let { active = 'main' }: Props = $props();

  const nav: { id: NavId; label: string; href: string; count?: string; d: string }[] = [
    { id: 'main', label: 'Übersicht', href: '#/', d: icons.grid },
    { id: 'hosts', label: 'Proxy-Hosts', href: '#/hosts', count: '18', d: icons.globe },
    { id: 'users', label: 'Nutzer', href: '#/users', count: '6', d: icons.users },
    { id: 'devices', label: 'Geräte', href: '#/devices', count: '7', d: icons.device },
    { id: 'access', label: 'Zugriff', href: '#/access', d: icons.lock },
    { id: 'nodes', label: 'Nodes', href: '#/nodes', count: '4', d: icons.server },
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

  <div class="ca">
    <span class="eyebrow">Zertifizierungsstelle</span>
    <div class="stack tight">
      <span class="ca-name">Tesseract Root CA</span>
      <span class="muted small">offline gespeichert · bis 03/2036</span>
    </div>
    <div class="stack tight">
      <span class="ca-name">Geräte-Intermediate</span>
      <span class="muted small">signiert Geräte · bis 11/2028</span>
    </div>
    <a href="#/settings-ca" class="ca-link">CA verwalten</a>
  </div>

  <div class="brand user">
    <div class="avatar">AD</div>
    <div class="stack">
      <span class="user-name">admin</span>
      <span class="muted small">Controller v0.4</span>
    </div>
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
  .stack.tight {
    gap: 2px;
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
  .ca {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 14px;
    border: 1px solid #262b35;
    border-radius: var(--radius-md);
    background: var(--surface);
  }
  .eyebrow {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .ca-name {
    font-size: 13px;
    font-weight: 600;
  }
  .ca-link {
    font-size: 13px;
    font-weight: 500;
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

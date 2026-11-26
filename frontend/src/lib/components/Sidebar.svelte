<script lang="ts">
  import { locale, t } from '../i18n';
  import Icon from './Icon.svelte';
  import { icons } from '../icons';
  import { session } from '../session.svelte';
  import { counts } from '../counts.svelte';
  import { pageAllowed } from '../permissions';
  import { UI_ROLES } from '../api';

  // Profil: Person mit Zahnrad-Andeutung
  const PROFILE_ICON = 'M12 12a4 4 0 1 0 0-8a4 4 0 0 0 0 8zM4 20c0-3.3 3.6-6 8-6s8 2.7 8 6';

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
    | 'settings'
    | 'me'
    | 'profile'
    | 'waf';

  interface Props {
    active?: NavId;
  }

  let { active = 'main' }: Props = $props();

  // Zahlen bei jedem Seitenwechsel auffrischen (z. B. nach dem Anlegen eines Hosts)
  $effect(() => {
    void active;
    if (session.user && session.isAdmin) counts.refresh();
  });

  const COUNT_OF: Partial<Record<NavId, keyof NonNullable<typeof counts.value>>> = {
    hosts: 'hosts',
    users: 'persons',
    devices: 'devices',
    nodes: 'nodes'
  };

  function countFor(id: NavId): string | undefined {
    const key = COUNT_OF[id];
    const v = key && counts.value ? counts.value[key] : undefined;
    return v === undefined ? undefined : v.toLocaleString(locale);
  }

  const nav: { id: NavId; label: string; href: string; d: string }[] = [
    { id: 'main', label: t('Übersicht'), href: '#/', d: icons.grid },
    { id: 'hosts', label: t('Proxy-Hosts'), href: '#/hosts', d: icons.globe },
    { id: 'certificates', label: t('Zertifikate'), href: '#/certificates', d: icons.okCircle },
    { id: 'users', label: t('Nutzer'), href: '#/users', d: icons.users },
    { id: 'devices', label: t('Geräte'), href: '#/devices', d: icons.device },
    { id: 'access', label: t('Zugriff'), href: '#/access', d: icons.lock },
    { id: 'nodes', label: t('Nodes'), href: '#/nodes', d: icons.server },
    { id: 'stats', label: t('Statistik'), href: '#/stats', d: icons.chart },
    { id: 'waf', label: t('WAF-Regeln'), href: '#/waf', d: icons.shield },
    { id: 'audit', label: t('Audit-Log'), href: '#/audit', d: icons.clipboard },
    { id: 'settings', label: t('Einstellungen'), href: '#/settings', d: icons.sliders },
    { id: 'me', label: t('Mein Zugang'), href: '#/me', d: icons.device }
  ];
  // Personen per Zertifikat sehen nur, was ihre Rolle erlaubt; „Mein Zugang“ nur sie
  const shown = $derived(
    nav.filter((item) =>
      item.id === 'me'
        ? session.viaCert
        : pageAllowed(session.user?.role, item.href.replace(/^#\//, ''))
    )
  );
</script>

<nav aria-label={t('Hauptnavigation')} class="sidebar">
  <div class="brand">
    <div class="logo">
      <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" style="stroke: var(--bg)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h18v18H3z"></path><path d="M8 8h8v8H8z"></path><path d="M3 3l5 5M21 3l-5 5M3 21l5-5M21 21l-5-5"></path></svg>
    </div>
    <div class="stack">
      <span class="brand-name">{t('Tesseract')}</span>
      <span class="muted small">{t('Caddy-Verwaltung')}</span>
    </div>
  </div>

  <div class="items">
    {#each shown as item (item.id)}
      <a href={item.href} class="item" class:current={item.id === active} aria-current={item.id === active ? 'page' : undefined}>
        <Icon d={item.d} />
        <span class="label">{item.label}</span>
        {#if countFor(item.id) !== undefined}<span class="count">{countFor(item.id)}</span>{/if}
      </a>
    {/each}
  </div>

  <div class="brand user">
    <div class="avatar">{(session.user?.username ?? '?').slice(0, 2).toUpperCase()}</div>
    <div class="stack grow">
      <span class="user-name">{session.user?.username ?? t('nicht angemeldet')}</span>
      <span class="muted small">
        {session.viaCert ? `${session.user?.device ?? ''} · ${UI_ROLES[session.role]}` : t('Controller')}
      </span>
    </div>
    <a
      href="#/profile"
      class="logout"
      class:on={active === 'profile'}
      aria-current={active === 'profile' ? 'page' : undefined}
      aria-label={t('Profil: Sprache und Farbschema')}
      title={t('Profil: Sprache und Farbschema')}
    >
      <Icon d={PROFILE_ICON} />
    </a>
    {#if session.user && !session.viaCert}
      <button type="button" class="logout" onclick={() => session.logout()} aria-label={t('Abmelden')} title={t('Abmelden')}>
        <Icon d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10" />
      </button>
    {/if}
  </div>
</nav>

<style>
  .sidebar {
    width: 100%;
    min-height: 100%;
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
    background: var(--surface-hover);
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
  /* Profil und Abmelden ganz unten in der Seitenleiste */
  .user {
    margin-top: auto;
    padding-top: 14px;
    border-top: 1px solid var(--border);
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
  .logout:hover,
  .logout.on {
    color: var(--text);
  }
  .logout.on {
    background: var(--surface-active);
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

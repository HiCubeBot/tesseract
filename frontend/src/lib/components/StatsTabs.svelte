<script lang="ts">
  import { t } from '../i18n';
  interface Props {
    current: string;
  }

  let { current }: Props = $props();

  const tabs = [
    { href: '#/stats', label: t('Sicherheit') },
    { href: '#/stats-traffic', label: t('Traffic & Leistung') },
    { href: '#/stats-usage', label: t('Nutzung') },
    { href: '#/stats-map', label: t('Karte') },
    { href: '#/stats-ops', label: t('Betrieb') },
    { href: '#/logs', label: t('Logs') }
  ];
</script>

<nav class="tabs" aria-label={t('Statistik')}>
  {#each tabs as item (item.href)}
    <a href={item.href} aria-current={item.href === current ? 'page' : undefined}>{item.label}</a>
  {/each}
</nav>

<style>
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    border-bottom: 1px solid var(--border);
  }
  a {
    padding: 10px 14px;
    color: var(--text-muted);
    text-decoration: none;
    font-weight: 500;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
  }
  a[aria-current='page'] {
    color: var(--text);
    border-bottom-color: var(--accent);
  }
</style>

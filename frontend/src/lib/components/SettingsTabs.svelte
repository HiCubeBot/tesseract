<script lang="ts">
  interface Props {
    current: string;
  }

  let { current }: Props = $props();

  const tabs = [
    { href: '#/settings', label: 'Allgemein' },
    { href: '#/settings-ca', label: 'Zertifizierungsstelle' },
    { href: '#/settings-integrations', label: 'Integrationen' },
    { href: '#/settings-notify', label: 'Benachrichtigungen' },
    { href: '#/settings-metrics', label: 'Metriken' },
    { href: '#/settings-backup', label: 'Backup' }
  ];
</script>

<nav class="tabs" aria-label="Bereiche">
  {#each tabs as t (t.href)}
    <a href={t.href} aria-current={t.href === current ? 'page' : undefined}>{t.label}</a>
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

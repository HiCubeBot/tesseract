<script lang="ts">
  interface Props {
    current: string;
  }

  let { current }: Props = $props();

  const tabs = [
    { href: '#/stats', label: 'Sicherheit' },
    { href: '#/stats-traffic', label: 'Traffic & Leistung' },
    { href: '#/stats-usage', label: 'Nutzung' },
    { href: '#/stats-map', label: 'Karte' },
    { href: '#/logs', label: 'Logs' }
  ];
</script>

<nav class="tabs" aria-label="Statistik">
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

<script lang="ts">
  import { t } from '../i18n';
  interface Props {
    current: string;
  }

  let { current }: Props = $props();

  const tabs = [
    { href: '#/settings', label: t('Allgemein') },
    { href: '#/settings-auth', label: t('Anmeldung') },
    { href: '#/settings-ldap', label: 'LDAP' },
    { href: '#/settings-ca', label: t('Zertifizierungsstelle') },
    { href: '#/settings-integrations', label: t('Integrationen') },
    { href: '#/settings-notify', label: t('Benachrichtigungen') },
    { href: '#/settings-metrics', label: t('Metriken') },
    { href: '#/settings-backup', label: t('Backup') }
  ];
</script>

<nav class="tabs" aria-label={t('Bereiche')}>
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

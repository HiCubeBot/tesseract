<script lang="ts">
  import Icon from './Icon.svelte';
  import Button from './Button.svelte';

  interface Props {
    icon?: 'devices' | 'hosts' | 'logs' | 'users';
    title?: string;
    text?: string;
    actionLabel?: string;
    actionHref?: string;
  }

  let { icon = 'devices', title = '', text = '', actionLabel = '', actionHref = '' }: Props = $props();

  const iconName = $derived(
    ({ devices: 'device', hosts: 'globe', logs: 'clipboard', users: 'users' } as const)[icon]
  );
</script>

<div class="empty">
  <div class="icon"><Icon name={iconName} size={22} color="#C9CED8" /></div>
  <h3>{title}</h3>
  {#if text}<p>{text}</p>{/if}
  {#if actionLabel}
    <div class="action">
      <Button variant="secondary" icon="plus" label={actionLabel} href={actionHref} />
    </div>
  {/if}
</div>

<style>
  .empty {
    width: 100%;
    min-height: 240px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 28px 24px;
    border-radius: var(--radius-lg);
    border: 1px dashed var(--border-dashed);
    background: var(--sidebar);
    font-family: var(--font-sans);
    color: var(--text);
    text-align: center;
  }
  .icon {
    width: 48px;
    height: 48px;
    border-radius: var(--radius-lg);
    background: var(--surface-raised);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  h3 {
    margin: 4px 0 0;
    font-size: 16px;
    font-weight: 600;
  }
  p {
    margin: 0;
    max-width: 360px;
    font-size: 14px;
    color: var(--text-muted);
    line-height: 1.5;
  }
  .action {
    margin-top: 6px;
  }
</style>

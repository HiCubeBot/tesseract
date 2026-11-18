<script lang="ts">
  import Icon from './Icon.svelte';

  interface Props {
    tone?: 'info' | 'ok' | 'warn' | 'bad';
    title?: string;
    text?: string;
    actionLabel?: string;
    actionHref?: string;
  }

  let { tone = 'info', title = '', text = '', actionLabel = '', actionHref = '' }: Props = $props();

  const iconName = $derived(
    ({ info: 'info', ok: 'okCircle', warn: 'warn', bad: 'badCircle' } as const)[tone]
  );
</script>

<div class="alert {tone}" role={tone === 'bad' ? 'alert' : 'status'}>
  <span class="icon"><Icon name={iconName} size={20} strokeWidth={2} /></span>
  <div class="body">
    <span class="title">{title}</span>
    {#if text}<span class="text">{text}</span>{/if}
  </div>
  {#if actionLabel && actionHref}
    <a class="action" href={actionHref}>{actionLabel}</a>
  {/if}
</div>

<style>
  .alert {
    --c: var(--accent-text);
    --bg-c: rgba(139, 124, 246, 0.1);
    --bd: rgba(139, 124, 246, 0.35);
    width: 100%;
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 12px;
    padding: 14px 16px;
    border-radius: var(--radius-md);
    font-family: var(--font-sans);
    background: var(--bg-c);
    border: 1px solid var(--bd);
  }
  .ok { --c: var(--ok-text); --bg-c: rgba(76, 195, 138, 0.08); --bd: rgba(76, 195, 138, 0.32); }
  .warn { --c: var(--warn-text); --bg-c: rgba(229, 164, 67, 0.1); --bd: rgba(229, 164, 67, 0.36); }
  .bad { --c: var(--bad-text); --bg-c: rgba(240, 113, 103, 0.1); --bd: rgba(240, 113, 103, 0.38); }
  .icon {
    color: var(--c);
    flex-shrink: 0;
    margin-top: 1px;
    display: inline-flex;
  }
  .body {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
  }
  .text {
    font-size: 13px;
    color: var(--text-soft);
    line-height: 1.45;
  }
  .action {
    flex-shrink: 0;
    align-self: center;
    display: inline-flex;
    align-items: center;
    min-height: 36px;
    padding: 0 12px;
    border-radius: var(--radius);
    border: 1px solid var(--bd);
    color: var(--c);
    font-size: 13px;
    font-weight: 600;
    text-decoration: none;
    white-space: nowrap;
  }
</style>

<script lang="ts">
  import Icon from './Icon.svelte';
  import type { IconName } from '../icons';

  interface Props {
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
    size?: 'md' | 'sm';
    icon?: IconName | 'none';
    label?: string;
    /** gesetzt → wird als Link gerendert */
    href?: string;
    type?: 'button' | 'submit' | 'reset';
    disabled?: boolean;
    onClick?: () => void;
  }

  let {
    variant = 'primary',
    size = 'md',
    icon = 'none',
    label = '',
    href = '',
    type = 'button',
    disabled = false,
    onClick
  }: Props = $props();

  const showIcon = $derived(icon && icon !== 'none');
</script>

{#if href}
  <a {href} class="btn {variant} {size}" aria-disabled={disabled || undefined}>
    {#if showIcon}<Icon name={icon as IconName} size={16} strokeWidth={2} />{/if}
    <span>{label}</span>
  </a>
{:else}
  <button {type} class="btn {variant} {size}" {disabled} onclick={() => !disabled && onClick?.()}>
    {#if showIcon}<Icon name={icon as IconName} size={16} strokeWidth={2} />{/if}
    <span>{label}</span>
  </button>
{/if}

<style>
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border-radius: var(--radius);
    text-decoration: none;
    white-space: nowrap;
    font-family: var(--font-sans);
    cursor: pointer;
    border: 1px solid transparent;
  }
  .md {
    min-height: 44px;
    padding: 0 16px;
    font-size: 14px;
  }
  .sm {
    min-height: 36px;
    padding: 0 12px;
    font-size: 13px;
  }
  .primary {
    background: var(--text);
    color: var(--bg);
    border-color: var(--text);
    font-weight: 600;
  }
  .secondary {
    background: var(--surface);
    color: var(--text);
    border-color: var(--border-input);
    font-weight: 500;
  }
  .ghost {
    background: transparent;
    color: var(--accent-text);
    font-weight: 500;
  }
  .danger {
    background: var(--bad-soft);
    color: var(--bad-text);
    border-color: rgba(240, 113, 103, 0.45);
    font-weight: 600;
  }
  .btn:disabled,
  .btn[aria-disabled='true'] {
    opacity: 0.45;
    cursor: not-allowed;
  }
</style>

<script lang="ts">
  import Icon from './Icon.svelte';

  interface Props {
    kind?: 'group' | 'person' | 'device';
    label?: string;
    removable?: boolean;
    onRemove?: () => void;
  }

  let { kind = 'person', label = '', removable = true, onRemove }: Props = $props();
  const iconName = $derived(kind === 'group' ? 'users' : kind === 'device' ? 'device' : 'person');
</script>

<span class="chip" class:group={kind === 'group'} class:removable>
  <Icon name={iconName} size={14} strokeWidth={2} />
  <span>{label}</span>
  {#if removable}
    <button type="button" aria-label="{label} entfernen" onclick={() => onRemove?.()}>
      <Icon name="close" size={12} strokeWidth={2.5} />
    </button>
  {/if}
</span>

<style>
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 34px;
    padding: 0 12px 0 10px;
    border-radius: var(--radius-pill);
    font-family: var(--font-sans);
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
    background: var(--surface-raised);
    color: var(--text);
  }
  .chip.removable {
    padding-right: 4px;
  }
  .chip.group {
    background: var(--accent-soft);
    color: var(--accent-text-hover);
  }
  button {
    width: 28px;
    height: 28px;
    padding: 0;
    border-radius: 50%;
    border: none;
    background: transparent;
    color: inherit;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  button:hover {
    background: rgba(255, 255, 255, 0.08);
  }
</style>

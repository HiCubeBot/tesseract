<script lang="ts">
  interface Props {
    /** Liste oder kommagetrennter Text */
    options?: string[] | string;
    /** ausgewählter Index (bindbar) */
    selected?: number;
    groupLabel?: string;
    onChange?: (index: number) => void;
  }

  let { options = [], selected = $bindable(0), groupLabel = 'Auswahl', onChange }: Props = $props();

  const list = $derived(
    Array.isArray(options) ? options : options.split(',').map((s) => s.trim()).filter(Boolean)
  );

  function pick(i: number) {
    selected = i;
    onChange?.(i);
  }
</script>

<div role="group" aria-label={groupLabel} class="seg">
  {#each list as label, i (i)}
    <button type="button" aria-pressed={i === selected} class:on={i === selected} onclick={() => pick(i)}>{label}</button>
  {/each}
</div>

<style>
  .seg {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 4px;
    padding: 4px;
    border-radius: var(--radius-md);
    background: var(--surface);
    border: 1px solid var(--border);
    font-family: var(--font-sans);
  }
  button {
    min-height: 36px;
    padding: 0 14px;
    border-radius: var(--radius-sm);
    border: none;
    font: inherit;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
    background: transparent;
    color: var(--text-muted);
  }
  button.on {
    background: var(--surface-active);
    color: var(--text);
  }
</style>

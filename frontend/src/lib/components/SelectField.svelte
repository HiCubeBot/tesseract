<script lang="ts">
  interface Props {
    label?: string;
    /** Liste oder kommagetrennter Text */
    options?: string[] | string;
    /** bindbar: bind:value */
    value?: string;
  }

  let { label = '', options = [], value = $bindable('') }: Props = $props();

  const id = $props.id();
  const list = $derived(
    Array.isArray(options) ? options : options.split(',').map((s) => s.trim()).filter(Boolean)
  );
</script>

<div class="field">
  <label for="{id}-select">{label}</label>
  <select id="{id}-select" bind:value>
    {#each list as option (option)}
      <option value={option}>{option}</option>
    {/each}
  </select>
</div>

<style>
  .field {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-family: var(--font-sans);
    font-size: 13px;
    color: var(--text-muted);
  }
  select {
    width: 100%;
    min-height: 44px;
    padding: 0 10px;
    border-radius: var(--radius);
    background: var(--bg);
    border: 1px solid var(--border-input);
    color: var(--text);
    font: inherit;
    font-size: 14px;
  }
</style>

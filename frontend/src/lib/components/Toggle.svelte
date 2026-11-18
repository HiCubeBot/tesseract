<script lang="ts">
  interface Props {
    label?: string;
    description?: string;
    /** bindbar: bind:checked */
    checked?: boolean;
    onChange?: (checked: boolean) => void;
  }

  let { label = '', description = '', checked = $bindable(false), onChange }: Props = $props();

  function toggle() {
    checked = !checked;
    onChange?.(checked);
  }
</script>

<button type="button" role="switch" aria-checked={checked} class="toggle" onclick={toggle}>
  <span class="text">
    <span class="label">{label}</span>
    {#if description}<span class="desc">{description}</span>{/if}
  </span>
  <span class="track" class:on={checked}><span class="knob"></span></span>
</button>

<style>
  .toggle {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    min-height: 64px;
    padding: 10px 14px;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    font-family: var(--font-sans);
    text-align: left;
    cursor: pointer;
  }
  .text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .label {
    font-size: 14px;
    font-weight: 500;
  }
  .desc {
    font-size: 13px;
    color: var(--text-muted);
  }
  .track {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: flex-start;
    width: 42px;
    height: 24px;
    padding: 3px;
    border-radius: var(--radius-pill);
    background: var(--border-dashed);
    transition: background 0.15s;
  }
  .track.on {
    background: var(--accent);
    justify-content: flex-end;
  }
  .knob {
    display: block;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #fff;
  }
</style>

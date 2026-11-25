<script lang="ts">
  import { t } from '../i18n';
  import { fmt } from '../stats';

  interface Item {
    label: string;
    value: number;
    /** Zusatz rechts neben dem Wert */
    note?: string;
    href?: string;
    mono?: boolean;
  }

  interface Props {
    items: Item[];
    color?: string;
    empty?: string;
  }

  let { items, color = '#8B7CF6', empty = t('Keine Daten im Zeitraum.') }: Props = $props();
  const max = $derived(Math.max(1, ...items.map((i) => i.value)));
</script>

{#if items.length === 0}
  <p class="muted small">{empty}</p>
{:else}
  <ul>
    {#each items as it (it.label)}
      <li>
        <div class="row-top">
          {#if it.href}<a href={it.href} class:mono={it.mono}>{it.label}</a>{:else}<span class:mono={it.mono}>{it.label}</span>{/if}
          <span class="value">{fmt(it.value)}{#if it.note} <span class="muted">· {it.note}</span>{/if}</span>
        </div>
        <div class="track"><div class="bar" style:width="{(it.value / max) * 100}%" style:background={color}></div></div>
      </li>
    {/each}
  </ul>
{/if}

<style>
  ul {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .row-top {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    font-size: 13px;
  }
  .row-top a,
  .row-top > span:first-child {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .value {
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .track {
    margin-top: 4px;
    height: 6px;
  }
  .bar {
    height: 6px;
    min-width: 2px;
    border-radius: 0 4px 4px 0;
  }
  .small {
    font-size: 13px;
    margin: 0;
  }
  .mono {
    font-family: var(--font-mono);
    font-size: 12px;
  }
</style>

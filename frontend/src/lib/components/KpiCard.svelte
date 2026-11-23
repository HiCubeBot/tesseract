<script lang="ts">
  // Kennzahl mit Veränderung zum Vorzeitraum und Verlaufslinie am unteren Rand.
  import Sparkline from './Sparkline.svelte';

  interface Props {
    label: string;
    value: string;
    sub?: string;
    /** Veränderung in Prozent zum Vorzeitraum (null = kein Vergleich) */
    delta?: number | null;
    /** true: Anstieg ist schlecht (z. B. Antwortzeit) */
    upIsBad?: boolean;
    tone?: 'neutral' | 'warn' | 'bad';
    spark?: (number | null)[];
    sparkColor?: string;
    selected?: boolean;
    onclick?: () => void;
  }

  let {
    label,
    value,
    sub = '',
    delta = null,
    upIsBad = false,
    tone = 'neutral',
    spark = [],
    sparkColor = 'var(--accent)',
    selected = false,
    onclick
  }: Props = $props();

  const deltaText = $derived(
    delta === null || !Number.isFinite(delta)
      ? ''
      : `${delta > 0 ? '▲' : delta < 0 ? '▼' : '±'} ${Math.abs(delta).toLocaleString('de-DE', { maximumFractionDigits: 1 })} %`
  );
  const deltaTone = $derived(delta === null || delta === 0 ? 'muted' : (delta > 0) !== upIsBad ? 'good' : 'bad');
</script>

<svelte:element
  this={onclick ? 'button' : 'div'}
  type={onclick ? 'button' : undefined}
  class="kpi {tone}"
  class:selected
  class:clickable={!!onclick}
  aria-pressed={onclick ? selected : undefined}
  role={onclick ? undefined : 'group'}
  aria-label={onclick ? undefined : label}
  {onclick}
>
  <span class="label">{label}</span>
  <span class="value-row">
    <span class="value">{value}</span>
    {#if deltaText}<span class="delta {deltaTone}">{deltaText}</span>{/if}
  </span>
  {#if sub}<span class="sub">{sub}</span>{/if}
  {#if spark.length > 1}
    <span class="spark"><Sparkline values={spark} width={200} height={28} fill dot={false} stretch color={sparkColor} /></span>
  {/if}
</svelte:element>

<style>
  .kpi {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    padding: 12px 14px 0;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--surface);
    color: var(--text);
    font: inherit;
    text-align: left;
    overflow: hidden;
  }
  .clickable {
    cursor: pointer;
  }
  .clickable:hover {
    border-color: var(--border-input);
  }
  .selected {
    border-color: var(--accent);
    box-shadow: inset 0 0 0 1px var(--accent);
  }
  .kpi.warn {
    border-color: rgba(229, 164, 67, 0.45);
  }
  .kpi.bad {
    border-color: rgba(240, 113, 103, 0.45);
  }
  .label {
    font-size: 12px;
    color: var(--text-muted);
  }
  .value-row {
    display: flex;
    align-items: baseline;
    gap: 8px;
    flex-wrap: wrap;
  }
  .value {
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.01em;
    font-variant-numeric: tabular-nums;
  }
  .delta {
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }
  .delta.good {
    color: var(--ok-text);
  }
  .delta.bad {
    color: var(--bad-text);
  }
  .delta.muted {
    color: var(--text-muted);
  }
  .sub {
    font-size: 12px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .spark {
    display: block;
    margin: 8px -14px 0;
    height: 28px;
  }
</style>

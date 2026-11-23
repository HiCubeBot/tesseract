<script lang="ts">
  // Erreichbarkeit je Tag als Balkenreihe: grün = ohne Ausfall, gelb = unter 30 Min.,
  // rot = ab 30 Min., grau = keine Daten.
  interface Day {
    day: string;
    checks?: number;
    pct: number | null;
    down_minutes: number;
    outages?: number;
  }

  interface Props {
    days: Day[];
    label: string;
    height?: number;
  }

  let { days, label, height = 22 }: Props = $props();

  function tone(d: Day): string {
    if (d.pct === null) return 'none';
    if (d.down_minutes === 0) return 'ok';
    return d.down_minutes < 30 ? 'warn' : 'bad';
  }

  function title(d: Day): string {
    const date = new Date(`${d.day}T00:00:00`).toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' });
    if (d.pct === null) return `${date}: keine Daten`;
    if (d.down_minutes === 0) return `${date}: ohne Ausfall`;
    const pct = d.pct.toLocaleString('de-DE', { maximumFractionDigits: 1 });
    return `${date}: ${d.down_minutes} Min. nicht erreichbar · ${pct} % des Tages erreichbar`;
  }
</script>

<div class="bars" role="img" aria-label={label} style:height="{height}px">
  {#each days as d (d.day)}
    <span class="bar {tone(d)}" title={title(d)}></span>
  {/each}
</div>

<style>
  .bars {
    display: flex;
    gap: 2px;
    align-items: stretch;
    min-width: 0;
  }
  .bar {
    flex: 1 1 0;
    min-width: 3px;
    border-radius: 2px;
    background: var(--surface-raised);
  }
  .bar.ok {
    background: #2f9e6b;
  }
  .bar.warn {
    background: #d9a23a;
  }
  .bar.bad {
    background: #d9604a;
  }
  .bar:hover {
    filter: brightness(1.2);
  }
</style>

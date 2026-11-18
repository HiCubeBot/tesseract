<script lang="ts">
  import { compact, fmt, niceMax, type Bucket } from '../stats';

  interface Series {
    key: string;
    label: string;
    color: string;
  }

  interface Props {
    buckets: Bucket[];
    series: Series[];
    height?: number;
    /** Name für Screenreader und Tabelle */
    label: string;
  }

  let { buckets, series, height = 180, label }: Props = $props();

  // In echter Pixelbreite zeichnen – gestreckt würden Schrift und Rundungen verzerrt
  let width = $state(0);
  const W = $derived(Math.max(320, width || 720));
  const PAD = { top: 8, right: 8, bottom: 22, left: 44 };
  let hover = $state<number | null>(null);
  let showTable = $state(false);

  const totals = $derived(buckets.map((b) => series.reduce((s, x) => s + (b.values[x.key] ?? 0), 0)));
  const max = $derived(niceMax(Math.max(0, ...totals)));
  const plotH = $derived(height - PAD.top - PAD.bottom);
  const slot = $derived((W - PAD.left - PAD.right) / Math.max(1, buckets.length));
  const barW = $derived(Math.min(24, slot * 0.7));
  const y = (v: number) => PAD.top + plotH - (v / max) * plotH;
  const labelEvery = $derived(Math.ceil(buckets.length / 8));

  /** Gestapelte Segmente eines Buckets – 2px Abstand, oben 4px rund */
  function segments(b: Bucket) {
    let acc = 0;
    const visible = series.filter((s) => (b.values[s.key] ?? 0) > 0);
    return visible.map((s, i) => {
      const v = b.values[s.key];
      const top = y(acc + v);
      const bottom = y(acc);
      acc += v;
      const gap = i > 0 ? 2 : 0;
      return { color: s.color, top, h: Math.max(1, bottom - top - gap), last: i === visible.length - 1 };
    });
  }

  function path(x: number, top: number, h: number, round: boolean): string {
    const r = round ? Math.min(4, h, barW / 2) : 0;
    const b = top + h;
    return `M${x},${b} V${top + r} Q${x},${top} ${x + r},${top} H${x + barW - r} Q${x + barW},${top} ${x + barW},${top + r} V${b} Z`;
  }
</script>

<figure class="chart">
  {#if series.length > 1}
    <div class="legend">
      {#each series as s (s.key)}<span><i style:background={s.color}></i>{s.label}</span>{/each}
    </div>
  {/if}
  <div class="plot" bind:clientWidth={width}>
    <svg viewBox="0 0 {W} {height}" role="img" aria-label={label} width={W} {height}>
      {#each [0, 0.5, 1] as f (f)}
        <line x1={PAD.left} x2={W - PAD.right} y1={y(max * f)} y2={y(max * f)} class="grid" />
        <text x={PAD.left - 8} y={y(max * f) + 4} class="tick" text-anchor="end">{compact(max * f)}</text>
      {/each}
      {#each buckets as b, i (i)}
        {@const x = PAD.left + i * slot + (slot - barW) / 2}
        {#each segments(b) as s, j (j)}
          <path d={path(x, s.top, s.h, s.last)} fill={s.color} opacity={hover === null || hover === i ? 1 : 0.45} />
        {/each}
        {#if i % labelEvery === 0 || i === buckets.length - 1}
          <text x={x + barW / 2} y={height - 6} class="tick" text-anchor="middle">{i === buckets.length - 1 ? 'jetzt' : b.label}</text>
        {/if}
        <rect
          x={PAD.left + i * slot}
          y={PAD.top}
          width={slot}
          height={plotH}
          fill="transparent"
          role="presentation"
          onmouseenter={() => (hover = i)}
          onmouseleave={() => (hover = null)}
        />
      {/each}
    </svg>
    {#if hover !== null}
      {@const b = buckets[hover]}
      <div class="tip" style:left="{((PAD.left + (hover + 0.5) * slot) / W) * 100}%">
        <strong>{b.title}</strong>
        {#each series as s (s.key)}
          {#if series.length > 1}<span><i style:background={s.color}></i>{s.label}: {fmt(b.values[s.key] ?? 0)}</span>{/if}
        {/each}
        <span class="sum">{series.length > 1 ? 'Summe' : series[0]?.label}: {fmt(totals[hover])}</span>
      </div>
    {/if}
  </div>
  <button type="button" class="table-toggle" aria-expanded={showTable} onclick={() => (showTable = !showTable)}>
    {showTable ? 'Tabelle ausblenden' : 'Als Tabelle'}
  </button>
  {#if showTable}
    <div class="table-wrap">
      <table class="table">
        <caption class="visually-hidden">{label}</caption>
        <thead><tr><th scope="col">Zeitraum</th>{#each series as s (s.key)}<th scope="col">{s.label}</th>{/each}</tr></thead>
        <tbody>
          {#each buckets as b, i (i)}
            {#if totals[i]}<tr><td>{b.title}</td>{#each series as s (s.key)}<td>{fmt(b.values[s.key] ?? 0)}</td>{/each}</tr>{/if}
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</figure>

<style>
  .chart {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    font-size: 12px;
    color: var(--text-muted);
  }
  .legend span,
  .tip span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  i {
    display: inline-block;
    width: 9px;
    height: 9px;
    border-radius: 3px;
  }
  .plot {
    position: relative;
  }
  svg {
    width: 100%;
    display: block;
  }
  .grid {
    stroke: #232833;
    stroke-width: 1;
    vector-effect: non-scaling-stroke;
  }
  .tick {
    fill: var(--text-muted);
    font-size: 11px;
  }
  .tip {
    position: absolute;
    top: 0;
    transform: translateX(-50%);
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: 8px 10px;
    border-radius: var(--radius);
    background: var(--surface-raised);
    border: 1px solid var(--border);
    font-size: 12px;
    white-space: nowrap;
    pointer-events: none;
    z-index: 2;
  }
  .sum {
    color: var(--text-muted);
  }
  .table-toggle {
    align-self: flex-start;
    padding: 0;
    border: none;
    background: none;
    color: var(--text-muted);
    font: inherit;
    font-size: 12px;
    cursor: pointer;
    text-decoration: underline;
  }
</style>

<script lang="ts">
  // Liniendiagramm mit Fläche, wahlweise mit einer gestrichelten Vergleichslinie (Vorzeitraum).
  import { compact, fmt, niceMax, type Bucket } from '../stats';

  interface Series {
    key: string;
    label: string;
    color: string;
    /** gestrichelt, ohne Fläche (z. B. Vorzeitraum) */
    dashed?: boolean;
  }

  interface Props {
    buckets: Bucket[];
    series: Series[];
    height?: number;
    label: string;
    /** Wertformat im Tooltip und an der Achse */
    format?: (n: number) => string;
  }

  let { buckets, series, height = 200, label, format = fmt }: Props = $props();

  let width = $state(0);
  const W = $derived(Math.max(320, width || 720));
  const PAD = { top: 10, right: 10, bottom: 22, left: 48 };
  let hover = $state<number | null>(null);

  const max = $derived(niceMax(Math.max(0, ...buckets.flatMap((b) => series.map((s) => b.values[s.key] ?? 0)))));
  const plotH = $derived(height - PAD.top - PAD.bottom);
  const plotW = $derived(W - PAD.left - PAD.right);
  const x = (i: number) => PAD.left + (buckets.length > 1 ? (i / (buckets.length - 1)) * plotW : plotW / 2);
  const y = (v: number) => PAD.top + plotH - (v / max) * plotH;
  // höchstens eine Beschriftung je ~70 px, damit sich nichts überlappt
  const labelEvery = $derived(Math.ceil(buckets.length / Math.max(2, Math.min(8, Math.floor(W / 70)))));

  /** Weiche Kurve (monoton, ohne Überschwinger unter 0) */
  function curve(pts: [number, number][]): string {
    if (!pts.length) return '';
    let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1];
      const [x1, y1] = pts[i];
      const cx = (x0 + x1) / 2;
      d += ` C${cx.toFixed(1)},${y0.toFixed(1)} ${cx.toFixed(1)},${y1.toFixed(1)} ${x1.toFixed(1)},${y1.toFixed(1)}`;
    }
    return d;
  }

  const paths = $derived(
    series.map((s) => {
      const pts = buckets.map((b, i) => [x(i), y(b.values[s.key] ?? 0)] as [number, number]);
      const line = curve(pts);
      const area = pts.length ? `${line} L${x(buckets.length - 1).toFixed(1)},${y(0)} L${x(0).toFixed(1)},${y(0)} Z` : '';
      return { ...s, line, area };
    })
  );

  function onMove(e: PointerEvent) {
    const svg = e.currentTarget as SVGElement;
    const r = svg.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    if (buckets.length < 2) return;
    const i = Math.round(((px - PAD.left) / plotW) * (buckets.length - 1));
    hover = Math.max(0, Math.min(buckets.length - 1, i));
  }

  const gid = `lc${Math.random().toString(36).slice(2, 8)}`;
</script>

<figure class="chart">
  <div class="legend">
    {#each series as s (s.key)}<span><i class:dashed={s.dashed} style:--c={s.color}></i>{s.label}</span>{/each}
  </div>
  <div class="plot" bind:clientWidth={width}>
    <svg
      viewBox="0 0 {W} {height}"
      role="img"
      aria-label={label}
      width={W}
      {height}
      onpointermove={onMove}
      onpointerleave={() => (hover = null)}
    >
      <defs>
        {#each paths as p (p.key)}
          <linearGradient id="{gid}-{p.key}" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stop-color={p.color} stop-opacity="0.28" />
            <stop offset="1" stop-color={p.color} stop-opacity="0" />
          </linearGradient>
        {/each}
      </defs>
      {#each [0, 0.5, 1] as f (f)}
        <line x1={PAD.left} x2={W - PAD.right} y1={y(max * f)} y2={y(max * f)} class="grid" />
        <text x={PAD.left - 8} y={y(max * f) + 4} class="tick" text-anchor="end">{compact(max * f)}</text>
      {/each}
      {#each buckets as b, i (i)}
        {#if i % labelEvery === 0 && i < buckets.length - 1}
          <text x={x(i)} y={height - 6} class="tick" text-anchor="middle">{b.label}</text>
        {/if}
      {/each}
      {#if buckets.length}<text x={x(buckets.length - 1)} y={height - 6} class="tick" text-anchor="end">jetzt</text>{/if}
      {#each paths as p (p.key)}
        {#if !p.dashed}<path d={p.area} fill="url(#{gid}-{p.key})" />{/if}
        <path d={p.line} class="line" class:dashed={p.dashed} stroke={p.color} />
      {/each}
      {#if hover !== null}
        <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + plotH} class="cursor" />
        {#each paths as p (p.key)}
          <circle cx={x(hover)} cy={y(buckets[hover].values[p.key] ?? 0)} r="3.5" fill={p.color} />
        {/each}
      {/if}
    </svg>
    {#if hover !== null}
      {@const b = buckets[hover]}
      <div class="tip" style:left="{(x(hover) / W) * 100}%">
        <strong>{b.title}</strong>
        {#each series as s (s.key)}
          <span><i class:dashed={s.dashed} style:--c={s.color}></i>{s.label}: {format(b.values[s.key] ?? 0)}</span>
        {/each}
      </div>
    {/if}
  </div>
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
    width: 12px;
    height: 0;
    border-top: 2px solid var(--c);
  }
  i.dashed {
    border-top-style: dashed;
    opacity: 0.8;
  }
  .plot {
    position: relative;
  }
  svg {
    width: 100%;
    display: block;
    touch-action: pan-y;
  }
  .grid {
    stroke: var(--border);
    stroke-width: 1;
  }
  .tick {
    fill: var(--text-muted);
    font-size: 11px;
  }
  .line {
    fill: none;
    stroke-width: 2;
    stroke-linejoin: round;
  }
  .line.dashed {
    stroke-width: 1.5;
    stroke-dasharray: 4 4;
    opacity: 0.7;
  }
  .cursor {
    stroke: var(--text-muted);
    stroke-width: 1;
    opacity: 0.4;
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
</style>

<script lang="ts">
  // Kleine Verlaufslinie ohne Achsen, z. B. Anfragen der letzten 24 Stunden.
  interface Props {
    values: (number | null)[];
    width?: number;
    height?: number;
    /** Fläche unter der Linie */
    fill?: boolean;
    /** letzten Punkt hervorheben */
    dot?: boolean;
    color?: string;
    label?: string;
    /** auf die volle Breite des Elternelements strecken */
    stretch?: boolean;
  }

  let {
    values,
    width = 96,
    height = 24,
    fill = false,
    dot = true,
    color = 'var(--accent)',
    label = '',
    stretch = false
  }: Props = $props();

  const pad = 2;
  const pts = $derived.by(() => {
    const v = values.map((x) => x ?? 0);
    if (v.length < 2) return [] as [number, number][];
    const max = Math.max(...v, 1);
    const step = (width - pad * 2) / (v.length - 1);
    return v.map((y, i) => [pad + i * step, height - pad - (y / max) * (height - pad * 2)] as [number, number]);
  });
  const line = $derived(pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(''));
  const area = $derived(
    pts.length ? `${line}L${pts[pts.length - 1][0].toFixed(1)},${height}L${pts[0][0].toFixed(1)},${height}Z` : ''
  );
</script>

<svg
  class="spark"
  class:stretch
  preserveAspectRatio={stretch ? 'none' : undefined}
  {width}
  {height}
  viewBox={`0 0 ${width} ${height}`}
  role={label ? 'img' : undefined}
  aria-label={label || undefined}
  aria-hidden={label ? undefined : 'true'}
  style:--spark={color}
>
  {#if pts.length}
    {#if fill}<path d={area} class="area" />{/if}
    <path d={line} class="line" />
    {#if dot}<circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="2" class="dot" />{/if}
  {/if}
</svg>

<style>
  .spark {
    display: block;
    overflow: visible;
  }
  .stretch {
    width: 100%;
  }
  .line {
    vector-effect: non-scaling-stroke;
    fill: none;
    stroke: var(--spark);
    stroke-width: 1.5;
    stroke-linejoin: round;
    stroke-linecap: round;
  }
  .area {
    fill: var(--spark);
    opacity: 0.14;
  }
  .dot {
    fill: var(--spark);
  }
</style>

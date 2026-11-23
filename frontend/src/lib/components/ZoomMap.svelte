<script lang="ts">
  /**
   * Zoombare Herkunftskarte: Mausrad/Pinch bzw. Knöpfe zum Zoomen, Ziehen zum Verschieben.
   * Punkte: Städte (mit Stadt-Datenbank) oder Länder. Nahe Punkte werden je nach Zoom zu einem
   * Kreis zusammengefasst („Karlsruhe +35“). Kartendaten aus dem eigenen Build (Natural Earth).
   */
  import { geoArea, geoNaturalEarth1, geoPath } from 'd3-geo';
  import { feature } from 'topojson-client';
  import type { Feature, FeatureCollection, Geometry, MultiPolygon, Polygon } from 'geojson';
  import { NAME_TO_ALPHA2, NUMERIC_TO_ALPHA2 } from '../geo';
  import { countryName } from '../api';
  import { fmt } from '../stats';

  interface Point {
    key: string;
    label: string;
    country: string;
    count: number;
    lat?: number;
    lon?: number;
  }

  interface Props {
    points: Point[];
    label: string;
    color?: string;
    /** Wort für den Tooltip, z. B. „Anfragen“ */
    unit?: string;
    /** ausgewähltes Land (ISO-Code) – wird hervorgehoben und herangezoomt */
    selected?: string | null;
    /** Klick auf ein Land (bzw. ins Meer: null) */
    onSelect?: (code: string | null) => void;
  }

  let { points, label, color = '#8B7CF6', unit = 'Anfragen', selected = null, onSelect }: Props = $props();

  type Country = Feature<Geometry, { name: string }> & { code: string };
  let countries = $state<Country[]>([]);
  let width = $state(0);

  import('world-atlas/countries-110m.json').then((m) => {
    const topo = m.default as unknown as Parameters<typeof feature>[0] & { objects: { countries: never } };
    const fc = feature(topo, topo.objects.countries) as unknown as FeatureCollection<Geometry, { name: string }>;
    countries = fc.features
      .map((f) => ({ ...f, code: NUMERIC_TO_ALPHA2[String(f.id)] ?? NAME_TO_ALPHA2[f.properties.name] ?? '' }))
      .filter((f) => f.code !== 'AQ');
  });

  const W = $derived(Math.max(300, width || 800));
  const H = $derived(Math.round(W * 0.52));
  const projection = $derived(
    countries.length
      ? geoNaturalEarth1().fitSize([W, H], { type: 'FeatureCollection', features: countries } as FeatureCollection)
      : null
  );
  const path = $derived(projection ? geoPath(projection) : null);
  const byCode = $derived(new Map(countries.map((c) => [c.code, c])));

  // Ansicht: Zoomfaktor k und Verschiebung (tx, ty) in SVG-Koordinaten
  let k = $state(1);
  let tx = $state(0);
  let ty = $state(0);
  const MAX_K = 40;

  function clampView() {
    tx = Math.min(0, Math.max(W - W * k, tx));
    ty = Math.min(0, Math.max(H - H * k, ty));
  }

  function zoomAt(factor: number, cx: number, cy: number) {
    const nk = Math.max(1, Math.min(MAX_K, k * factor));
    const f = nk / k;
    tx = cx - (cx - tx) * f;
    ty = cy - (cy - ty) * f;
    k = nk;
    clampView();
  }

  function svgPoint(e: { clientX: number; clientY: number }, el: Element): [number, number] {
    const r = el.getBoundingClientRect();
    return [((e.clientX - r.left) / r.width) * W, ((e.clientY - r.top) / r.height) * H];
  }

  function onWheel(e: WheelEvent) {
    e.preventDefault();
    const [x, y] = svgPoint(e, e.currentTarget as Element);
    // stufenlos: ein Rastschritt (≈100) ≈ Faktor 1,2; Trackpads liefern kleine Werte
    const dy = e.deltaMode === 1 ? e.deltaY * 33 : e.deltaY;
    zoomAt(Math.exp(-Math.max(-300, Math.min(300, dy)) * 0.0018), x, y);
  }

  // Mausrad nicht passiv anmelden – sonst scrollt die Seite statt zu zoomen
  let svgEl = $state<SVGSVGElement | null>(null);
  $effect(() => {
    const el = svgEl;
    if (!el) return;
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  });

  // Ziehen und Pinch-Zoom mit Pointer-Events
  const pointers = new Map<number, [number, number]>();
  let pinchDist = 0;
  // Klick statt Ziehen: kaum bewegt zwischen Drücken und Loslassen
  let downAt: [number, number] | null = null;
  let moved = 0;
  let grabbing = $state(false);

  function onDown(e: PointerEvent) {
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, svgPoint(e, e.currentTarget as Element));
    grabbing = true;
    downAt = pointers.size === 1 ? [e.clientX, e.clientY] : null;
    moved = 0;
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinchDist = Math.hypot(a[0] - b[0], a[1] - b[1]);
    }
  }

  function onMove(e: PointerEvent) {
    if (!pointers.has(e.pointerId)) return;
    const p = svgPoint(e, e.currentTarget as Element);
    const prev = pointers.get(e.pointerId)!;
    pointers.set(e.pointerId, p);
    if (pointers.size === 1) {
      const dx = p[0] - prev[0];
      const dy = p[1] - prev[1];
      moved += Math.abs(dx) + Math.abs(dy);
      tx += dx;
      ty += dy;
      clampView();
    } else if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (pinchDist) zoomAt(d / pinchDist, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
      pinchDist = d;
    }
  }

  function onUp(e: PointerEvent) {
    const wasClick = downAt !== null && pointers.size === 1 && moved < 4 && e.type === 'pointerup';
    pointers.delete(e.pointerId);
    downAt = null;
    if (wasClick && onSelect) {
      // Wegen Pointer-Capture kommt der Klick am SVG an – Land unter dem Zeiger suchen
      const el = document.elementsFromPoint(e.clientX, e.clientY).find((x) => x instanceof SVGPathElement && x.dataset.code);
      const code = (el as SVGPathElement | undefined)?.dataset.code ?? null;
      onSelect(code && code === selected ? null : code);
    }
    if (pointers.size < 2) pinchDist = 0;
    if (pointers.size === 0) grabbing = false;
  }

  function reset() {
    k = 1;
    tx = 0;
    ty = 0;
  }

  /** An ein Land heranzoomen (größtes Teilstück, damit Frankreich nicht in der Karibik endet) */
  function zoomTo(code: string) {
    const f = byCode.get(code);
    if (!f || !path) return;
    let g: Geometry = f.geometry;
    if (g.type === 'MultiPolygon') {
      const parts = (g as MultiPolygon).coordinates.map((c) => ({ type: 'Polygon', coordinates: c }) as Polygon);
      g = parts.reduce((a, b) => (geoArea(b) > geoArea(a) ? b : a));
    }
    const [[x0, y0], [x1, y1]] = path.bounds(g as never);
    const nk = Math.max(1, Math.min(MAX_K, 0.7 / Math.max((x1 - x0) / W, (y1 - y0) / H, 0.001)));
    k = nk;
    tx = W / 2 - nk * ((x0 + x1) / 2);
    ty = H / 2 - nk * ((y0 + y1) / 2);
    clampView();
  }

  // Auswahl von außen (Klick auf der Karte oder in der Liste): heranzoomen
  let zoomedFor: string | null = null;
  $effect(() => {
    const code = selected;
    if (!path || code === zoomedFor) return;
    zoomedFor = code;
    if (code) zoomTo(code);
    else reset();
  });

  /** Mittelpunkt des größten Teilstücks eines Landes */
  function anchor(f: Country): [number, number] | null {
    if (!path) return null;
    let g: Geometry = f.geometry;
    if (g.type === 'MultiPolygon') {
      const parts = (g as MultiPolygon).coordinates.map((c) => ({ type: 'Polygon', coordinates: c }) as Polygon);
      g = parts.reduce((a, b) => (geoArea(b) > geoArea(a) ? b : a));
    }
    const c = path.centroid(g as never);
    return Number.isFinite(c[0]) ? c : null;
  }

  // Punkte in Kartenkoordinaten (ohne Zoom)
  const placed = $derived.by(() => {
    if (!projection) return [];
    const out: (Point & { x: number; y: number })[] = [];
    for (const p of points) {
      let xy: [number, number] | null = null;
      if (p.lat != null && p.lon != null) xy = projection([p.lon, p.lat]) as [number, number] | null;
      else {
        const f = byCode.get(p.country);
        xy = f ? anchor(f) : null;
      }
      if (xy && Number.isFinite(xy[0])) out.push({ ...p, x: xy[0], y: xy[1] });
    }
    return out;
  });

  // Zusammenfassen: Punkte, die bei aktuellem Zoom näher als 22 px liegen
  const clusters = $derived.by(() => {
    const sorted = [...placed].sort((a, b) => b.count - a.count);
    const out: { x: number; y: number; count: number; lead: (typeof sorted)[number]; members: number }[] = [];
    const R = 22 / k;
    for (const p of sorted) {
      const c = out.find((o) => Math.hypot(o.lead.x - p.x, o.lead.y - p.y) < R);
      if (c) {
        c.count += p.count;
        c.members += 1;
      } else out.push({ x: p.x, y: p.y, count: p.count, lead: p, members: 1 });
    }
    return out;
  });
  const max = $derived(Math.max(1, ...clusters.map((c) => c.count)));
  const radius = (n: number) => Math.max(3, Math.sqrt(n / max) * Math.min(28, W / 30));
  const labelled = $derived(new Set(clusters.slice(0, 8).map((c) => c.lead.key)));
  const active = $derived(new Set(points.map((p) => p.country)));

  let hover = $state<(typeof clusters)[number] | null>(null);
  const sx = (x: number) => x * k + tx;
  const sy = (y: number) => y * k + ty;
</script>

<figure class="map" bind:clientWidth={width}>
  {#if path}
    <div class="frame">
      <svg
        width={W}
        height={H}
        viewBox="0 0 {W} {H}"
        role="img"
        aria-label={label}
        class:grabbing
        bind:this={svgEl}
        onpointerdown={onDown}
        onpointermove={onMove}
        onpointerup={onUp}
        onpointercancel={onUp}
        ondblclick={(e) => {
          const [x, y] = svgPoint(e, e.currentTarget as Element);
          zoomAt(2, x, y);
        }}
      >
        <g transform="translate({tx} {ty}) scale({k})">
          {#each countries as c (c.id ?? c.properties.name)}
            <path
              d={path(c) ?? ''}
              data-code={c.code || undefined}
              class="land"
              class:active={active.has(c.code)}
              class:selected={selected === c.code}
              class:clickable={!!onSelect && !!c.code}
              style:stroke-width={(selected === c.code ? 1.6 : 0.6) / k}
            />
          {/each}
        </g>
        {#each clusters as c (c.lead.key)}
          {@const r = radius(c.count)}
          <circle
            cx={sx(c.x)}
            cy={sy(c.y)}
            {r}
            fill={color}
            class="bubble"
            class:dim={hover !== null && hover !== c}
            role="presentation"
            onpointerenter={() => (hover = c)}
            onpointerleave={() => (hover = null)}
          />
        {/each}
        {#each clusters as c (c.lead.key)}
          {#if labelled.has(c.lead.key)}
            {@const r = radius(c.count)}
            <text x={sx(c.x) + r + 4} y={sy(c.y) + 4} class="lbl">
              {c.lead.label}{c.members > 1 ? ` +${c.members - 1}` : ''} <tspan class="n">{fmt(c.count)}</tspan>
            </text>
          {/if}
        {/each}
      </svg>
      <div class="zoom" role="group" aria-label="Zoom">
        <button type="button" aria-label="Hineinzoomen" onclick={() => zoomAt(1.6, W / 2, H / 2)}>+</button>
        <button type="button" aria-label="Herauszoomen" onclick={() => zoomAt(1 / 1.6, W / 2, H / 2)}>−</button>
        <button type="button" aria-label="Ganze Welt" title="Ganze Welt" onclick={reset} disabled={k === 1}>⌂</button>
      </div>
      {#if hover}
        <div class="tip" style:left="{(sx(hover.x) / W) * 100}%" style:top="{(sy(hover.y) / H) * 100}%">
          <strong>{hover.lead.label}{hover.members > 1 ? ` und ${hover.members - 1} weitere` : ''}</strong>
          {#if hover.lead.label !== countryName(hover.lead.country)}<span class="muted">{countryName(hover.lead.country)}</span>{/if}
          <span>{fmt(hover.count)} {unit}</span>
        </div>
      {/if}
    </div>
  {:else}
    <div class="loading" style:height="{H}px">Karte wird geladen …</div>
  {/if}
  <figcaption class="muted">
    Kreisfläche = Anzahl · Mausrad, Doppelklick oder +/− zum Zoomen, Ziehen zum Verschieben{onSelect ? ' · Land anklicken für Details' : ''}
  </figcaption>
</figure>

<style>
  .map {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .frame {
    position: relative;
    border-radius: var(--radius);
    overflow: hidden;
    background: var(--bg);
    border: 1px solid var(--border);
  }
  svg {
    display: block;
    width: 100%;
    height: auto;
    cursor: grab;
    touch-action: none;
    user-select: none;
  }
  svg.grabbing {
    cursor: grabbing;
  }
  .land {
    fill: color-mix(in srgb, var(--text) 9%, var(--surface));
    stroke: var(--surface);
  }
  .land.active {
    fill: color-mix(in srgb, var(--accent) 16%, var(--surface-raised));
  }
  .land.clickable {
    cursor: pointer;
  }
  .land.clickable:hover {
    fill: color-mix(in srgb, var(--accent) 26%, var(--surface-raised));
  }
  .land.selected {
    fill: color-mix(in srgb, var(--accent) 34%, var(--surface-raised));
    stroke: var(--accent);
  }
  .bubble {
    fill-opacity: 0.55;
    stroke: var(--surface);
    stroke-width: 1;
    transition: fill-opacity 0.15s;
  }
  .bubble.dim {
    fill-opacity: 0.25;
  }
  .lbl {
    font-size: 11px;
    fill: var(--text);
    paint-order: stroke;
    stroke: var(--surface);
    stroke-width: 3px;
    pointer-events: none;
  }
  .lbl .n {
    fill: var(--text-muted);
  }
  .zoom {
    position: absolute;
    right: 10px;
    top: 10px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .zoom button {
    width: 30px;
    height: 30px;
    border-radius: var(--radius);
    border: 1px solid var(--border-input);
    background: var(--surface);
    color: var(--text);
    font-size: 16px;
    line-height: 1;
    cursor: pointer;
  }
  .zoom button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .tip {
    position: absolute;
    transform: translate(-50%, calc(-100% - 12px));
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px 10px;
    border-radius: var(--radius);
    background: var(--surface-raised);
    border: 1px solid var(--border);
    font-size: 12px;
    white-space: nowrap;
    pointer-events: none;
  }
  .loading {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
  }
  figcaption {
    font-size: 11px;
  }
</style>

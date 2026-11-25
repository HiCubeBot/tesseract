<script lang="ts">
  import { t } from '../i18n';
  /**
   * Herkunftskarte: ein Kreis pro Land, Fläche ∝ Anzahl. Kartendaten (Natural Earth, 110m)
   * werden erst beim Anzeigen nachgeladen und liegen im eigenen Build – keine externe Anfrage.
   */
  import { geoArea, geoNaturalEarth1, geoPath } from 'd3-geo';
  import { feature } from 'topojson-client';
  import type { Feature, FeatureCollection, Geometry, MultiPolygon, Polygon } from 'geojson';
  import { NAME_TO_ALPHA2, NUMERIC_TO_ALPHA2 } from '../geo';
  import { countryName } from '../api';
  import { fmt } from '../stats';

  interface Props {
    items: { country: string; count: number }[];
    label: string;
    color?: string;
    /** Text im Tooltip, {0} = Anzahl – je nach Auswahl „Anfragen“, „abgelehnt“, „angenommen“ */
    countText?: string;
  }

  let { items, label, color = '#9085E9', countText = t('{0} Anfragen') }: Props = $props();

  type Country = Feature<Geometry, { name: string }> & { code: string };
  let countries = $state<Country[]>([]);
  let width = $state(0);
  let hover = $state<{ code: string; x: number; y: number } | null>(null);

  import('world-atlas/countries-110m.json').then((m) => {
    const topo = m.default as unknown as Parameters<typeof feature>[0] & { objects: { countries: never } };
    const fc = feature(topo, topo.objects.countries) as unknown as FeatureCollection<Geometry, { name: string }>;
    countries = fc.features
      .map((f) => ({ ...f, code: NUMERIC_TO_ALPHA2[String(f.id)] ?? NAME_TO_ALPHA2[f.properties.name] ?? '' }))
      // Antarktis spart Platz – von dort kommen keine Angriffe
      .filter((f) => f.code !== 'AQ');
  });

  const W = $derived(Math.max(280, width || 600));
  const H = $derived(Math.round(W * 0.48));
  const projection = $derived(
    countries.length
      ? geoNaturalEarth1().fitSize([W, H], { type: 'FeatureCollection', features: countries } as FeatureCollection)
      : null
  );
  const path = $derived(projection ? geoPath(projection) : null);

  /** Mittelpunkt des größten Teilstücks – sonst landet z. B. Frankreich im Atlantik */
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

  const byCode = $derived(new Map(countries.map((c) => [c.code, c])));
  const max = $derived(Math.max(1, ...items.map((i) => i.count)));
  const bubbles = $derived(
    items
      .map((i) => {
        const f = byCode.get(i.country);
        const p = f ? anchor(f) : null;
        // Fläche proportional zur Anzahl, kleinster Kreis bleibt sichtbar
        return p ? { ...i, x: p[0], y: p[1], r: Math.max(4, Math.sqrt(i.count / max) * Math.min(26, W / 28)) } : null;
      })
      .filter((b): b is NonNullable<typeof b> => b !== null)
      // große zuerst zeichnen, kleine liegen oben und bleiben anfahrbar
      .sort((a, b) => b.r - a.r)
  );
  const offMap = $derived(items.filter((i) => !byCode.has(i.country)));
  const active = $derived(new Set(items.map((i) => i.country)));
  const hovered = $derived(hover ? items.find((i) => i.country === hover!.code) : null);
</script>

<figure class="map" bind:clientWidth={width}>
  {#if path}
    <svg width={W} height={H} viewBox="0 0 {W} {H}" role="img" aria-label={label}>
      {#each countries as c (c.id ?? c.properties.name)}
        <!-- Klick öffnet Statistik › Karte mit diesem Land; per Tastatur über die Liste daneben -->
        <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
        <path
          d={path(c) ?? ''}
          class="land"
          class:active={active.has(c.code)}
          class:clickable={!!c.code}
          onclick={() => c.code && (location.hash = `#/stats-map?country=${c.code}`)}
        />
      {/each}
      {#each bubbles as b (b.country)}
        <circle
          cx={b.x}
          cy={b.y}
          r={b.r}
          fill={color}
          class="bubble"
          class:dim={hover !== null && hover.code !== b.country}
          role="presentation"
          onmouseenter={() => (hover = { code: b.country, x: b.x, y: b.y - b.r })}
          onmouseleave={() => (hover = null)}
        />
      {/each}
    </svg>
    {#if hover && hovered}
      <div class="tip" style:left="{hover.x}px" style:top="{hover.y}px">
        <strong>{countryName(hovered.country)}</strong>
        <span>{countText.replace('{0}', fmt(hovered.count))}</span>
      </div>
    {/if}
  {:else}
    <div class="loading" style:height="{H}px">{t('Karte wird geladen …')}</div>
  {/if}
  <figcaption class="muted">
    {t('Kreisfläche = Anzahl · GeoIP-Datenbank lokal')}{#if offMap.length} {t('· ohne Kartenpunkt: {0}', offMap
        .map((i) => `${countryName(i.country)} (${fmt(i.count)})`)
        .join(', '))}{/if}
  </figcaption>
</figure>

<style>
  .map {
    position: relative;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  svg {
    display: block;
    max-width: 100%;
    height: auto;
  }
  .land {
    fill: var(--surface-active);
    stroke: var(--surface);
    stroke-width: 0.5;
  }
  .land.clickable {
    cursor: pointer;
  }
  .land.clickable:hover {
    fill: color-mix(in srgb, var(--accent) 26%, var(--surface-raised));
  }
  .land.active {
    fill: var(--border-dashed);
  }
  .bubble {
    fill-opacity: 0.6;
    stroke: var(--surface);
    stroke-width: 2;
    cursor: default;
    transition: opacity 0.15s;
  }
  .bubble:hover {
    fill-opacity: 0.9;
  }
  .bubble.dim {
    opacity: 0.45;
  }
  .tip {
    position: absolute;
    transform: translate(-50%, calc(-100% - 8px));
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 6px 10px;
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
    font-size: 13px;
  }
  figcaption {
    font-size: 12px;
  }
</style>

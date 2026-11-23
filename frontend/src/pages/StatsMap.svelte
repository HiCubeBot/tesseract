<script lang="ts">
  // Statistik › Karte: zoombare Herkunftskarte mit Ländern, Städten und Netzbetreibern.
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import StatsTabs from '../lib/components/StatsTabs.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import ZoomMap from '../lib/components/ZoomMap.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import { api, countryName, type NodeInfo } from '../lib/api';
  import { fmt } from '../lib/stats';

  interface Geo {
    countries: { country: string; count: number }[];
    cities: { country: string; city: string; lat: number; lon: number; count: number }[];
    asns: { asn: number; org: string; count: number }[];
    unknown: number;
    geoip: boolean;
    cities_db: boolean;
    asn_db: boolean;
    geoip_attribution: string | null;
    selected: { country: string; requests: number; denied: number; hosts: { host: string; count: number }[] } | null;
  }

  const RANGES = ['24h', '7d', '30d'] as const;
  const WHICH = ['all', 'denied', 'allowed'] as const;
  const WHICH_LABELS = ['Alle', 'Abgelehnt', 'Angenommen'];
  const WHICH_COLORS = ['#3987E5', '#D95926', '#199E70'];
  let range = $state(0);
  let which = $state(0);
  let tab = $state(0);
  let node = $state('');
  let nodes = $state<NodeInfo[]>([]);
  let data = $state<Geo | null>(null);
  // Ausgewähltes Land: Städte, Netzbetreiber und Zusammenfassung nur dieses Landes.
  // Vorauswahl per Link, z. B. #/stats-map?country=DE
  let country = $state<string | null>(
    new URLSearchParams(location.hash.split('?')[1] ?? '').get('country')?.toUpperCase().slice(0, 2) || null
  );
  let detail = $state<Geo | null>(null);
  let error = $state('');
  let loading = $state(false);

  const query = () => `range=${RANGES[range]}&which=${WHICH[which]}&node=${encodeURIComponent(node)}`;

  async function loadDetail() {
    const c = country;
    if (!c) {
      detail = null;
      return;
    }
    try {
      const d = await api.get<Geo>(`/stats/geo?${query()}&country=${c}`);
      if (country === c) detail = d;
    } catch {
      detail = null;
    }
  }

  function select(code: string | null) {
    country = code;
    detail = null;
    if (code && tab === 0) tab = 1;
    if (!code) tab = 0;
    loadDetail();
  }

  // Link auf ein Land, während die Seite schon offen ist (gleiche Route, andere Abfrage)
  function onHash() {
    const c = new URLSearchParams(location.hash.split('?')[1] ?? '').get('country')?.toUpperCase().slice(0, 2) || null;
    if (location.hash.startsWith('#/stats-map') && c !== country) select(c);
  }

  async function load() {
    loading = true;
    loadDetail();
    try {
      data = await api.get<Geo>(`/stats/geo?${query()}`);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }
  load();
  api.get<NodeInfo[]>('/nodes').then((n) => (nodes = n.filter((x) => x.state !== 'pending')));

  // Städte, wenn vorhanden – sonst Länder als Punkte
  const points = $derived.by(() => {
    if (!data) return [];
    if (data.cities.length) {
      const pts = data.cities.map((c) => ({
        key: `${c.country}|${c.city}|${c.lat}|${c.lon}`,
        label: c.city,
        country: c.country,
        count: c.count,
        lat: c.lat,
        lon: c.lon
      }));
      // Länder-Anteil ohne Stadt (z. B. nur Land bekannt) als Länderpunkt dazu
      const inCities = new Map<string, number>();
      for (const c of data.cities) inCities.set(c.country, (inCities.get(c.country) ?? 0) + c.count);
      for (const c of data.countries) {
        const rest = c.count - (inCities.get(c.country) ?? 0);
        if (rest > 0 && !inCities.has(c.country)) pts.push({ key: c.country, label: countryName(c.country), country: c.country, count: rest } as never);
      }
      return pts;
    }
    return data.countries.map((c) => ({ key: c.country, label: countryName(c.country), country: c.country, count: c.count }));
  });

  const TABS = ['Länder', 'Städte', 'Netzbetreiber'];
  const list = $derived.by((): { key: string; label: string; note?: string; count: number; code?: string }[] => {
    if (!data) return [];
    if (tab === 0)
      return data.countries.slice(0, 40).map((c) => ({ key: c.country, label: countryName(c.country), count: c.count, code: c.country }));
    // Städte und Netzbetreiber: beim ausgewählten Land nur dessen
    const src = country ? detail : data;
    if (!src) return [];
    if (tab === 1)
      return src.cities
        .slice(0, 40)
        .map((c) => ({ key: `${c.country}|${c.city}|${c.lat}`, label: c.city, note: country ? undefined : countryName(c.country), count: c.count }));
    return src.asns.slice(0, 40).map((a) => ({ key: String(a.asn), label: a.org || `AS${a.asn}`, note: `AS${a.asn}`, count: a.count }));
  });
  const sel = $derived(detail?.selected ?? null);
  const listMax = $derived(Math.max(1, ...list.map((i) => i.count)));
  const total = $derived((data?.countries ?? []).reduce((s, c) => s + c.count, 0));
  const unit = $derived(['Anfragen', 'abgelehnt', 'angenommen'][which]);
</script>

<svelte:window onhashchange={onHash} />

<AppShell active="stats">
  <PageHeader title="Statistik" subtitle="Woher die Anfragen kommen – nach Land, Stadt und Netzbetreiber." />
  <StatsTabs current="#/stats-map" />

  <div class="row">
    <SegmentedControl groupLabel="Zeitraum" options={['Letzte 24 Stunden', '7 Tage', '30 Tage']} bind:selected={range} onChange={load} />
    <SegmentedControl groupLabel="Welche Anfragen" options={WHICH_LABELS} bind:selected={which} onChange={load} />
    <label class="node-select">
      <span>Node</span>
      <select class="input" bind:value={node} onchange={load}>
        <option value="">Alle Nodes</option>
        {#each nodes as n (n.id)}<option value={n.name}>{n.name}</option>{/each}
      </select>
    </label>
    {#if loading}<span class="muted small">lädt …</span>{/if}
  </div>

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if data && !data.geoip}
    <Alert
      tone="info"
      title="Keine GeoIP-Datenbank"
      text="Für die Karte eine Datenbank hinterlegen: TESSERACT_GEOIP_AUTO=dbip (Länder), dbip-city (mit Städten), jeweils wahlweise +asn (Netzbetreiber) – oder eine Datei mit TESSERACT_GEOIP_DB."
    />
  {/if}

  {#if data}
    <div class="layout">
      <section class="card map-card" aria-label="Karte">
        <ZoomMap
          {points}
          color={WHICH_COLORS[which]}
          {unit}
          selected={country}
          onSelect={select}
          label={`Weltkarte: ${WHICH_LABELS[which].toLowerCase()} Anfragen nach Herkunft`}
        />
        <p class="muted tiny">
          {fmt(total)} {unit} mit bekannter Herkunft{#if data.unknown} · {fmt(data.unknown)} ohne (private oder lokale Adressen){/if}
          {#if data.geoip && !data.cities_db} · Städte mit <span class="mono">TESSERACT_GEOIP_AUTO=dbip-city</span>{/if}
          {#if data.geoip_attribution} · <a href="https://db-ip.com" rel="noopener noreferrer" target="_blank">{data.geoip_attribution}</a>{/if}
        </p>
      </section>

      <section class="card side" aria-label="Rangliste">
        {#if country}
          <div class="detail">
            <div class="detail-head">
              <h2>{countryName(country)}</h2>
              <button type="button" class="clear" onclick={() => select(null)} aria-label="Auswahl aufheben" title="Alle Länder">×</button>
            </div>
            {#if sel}
              <dl>
                <div><dt>Anfragen</dt><dd>{fmt(sel.requests)}</dd></div>
                <div>
                  <dt>Abgelehnt</dt>
                  <dd class:warn={sel.denied > 0}>{fmt(sel.denied)}{sel.requests ? ` (${Math.round((100 * sel.denied) / sel.requests)} %)` : ''}</dd>
                </div>
              </dl>
              {#if sel.hosts.length}
                <span class="eyebrow">Häufigste Ziele</span>
                <ul class="hosts">
                  {#each sel.hosts as h (h.host)}
                    <li><span class="mono ellipsis">{h.host === '-' ? 'ohne Host' : h.host}</span><span class="val">{fmt(h.count)}</span></li>
                  {/each}
                </ul>
              {/if}
              <a class="small" href={`#/logs?q=${encodeURIComponent(`country:${country}`)}${which === 1 ? '&filter=denied' : ''}`}>Einträge in den Logs</a>
            {:else}
              <p class="muted small">Lädt …</p>
            {/if}
          </div>
        {/if}
        <SegmentedControl groupLabel="Liste" options={TABS} bind:selected={tab} />
        {#if list.length}
          <ul class="bars">
            {#each list as i (i.key)}
              <li>
                {#if i.code}
                  {@const code = i.code}
                  <button type="button" class="pick" class:on={country === code} onclick={() => select(country === code ? null : code)}>
                    <span class="bar-top">
                      <span class="ellipsis">{i.label}</span>
                      <span class="val">{fmt(i.count)}</span>
                    </span>
                    <span class="track"><span class="fill" style:width="{(i.count / listMax) * 100}%" style:background={WHICH_COLORS[which]}></span></span>
                  </button>
                {:else}
                  <div class="bar-top">
                    <span class="ellipsis">{i.label}{#if i.note} <span class="muted note">{i.note}</span>{/if}</span>
                    <span class="val">{fmt(i.count)}</span>
                  </div>
                  <div class="track"><div class="fill" style:width="{(i.count / listMax) * 100}%" style:background={WHICH_COLORS[which]}></div></div>
                {/if}
              </li>
            {/each}
          </ul>
        {:else}
          <p class="muted small">
            {#if tab === 1 && !data.cities_db && !data.cities.length}Städte gibt es nur mit einer Stadt-Datenbank (<span class="mono">TESSERACT_GEOIP_AUTO=dbip-city</span>).
            {:else if tab === 2 && !data.asn_db && !data.asns.length}Netzbetreiber gibt es nur mit einer ASN-Datenbank (<span class="mono">TESSERACT_GEOIP_AUTO=dbip+asn</span>).
            {:else if country && tab > 0}Keine {tab === 1 ? 'Städte' : 'Netzbetreiber'} für {countryName(country)} im Zeitraum.
            {:else}Keine Anfragen mit bekannter Herkunft im Zeitraum.{/if}
          </p>
        {/if}
      </section>
    </div>
  {/if}
</AppShell>

<style>
  .detail {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--border);
  }
  .detail-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .detail h2 {
    margin: 0;
    font-size: 18px;
  }
  .clear {
    width: 28px;
    height: 28px;
    border-radius: var(--radius);
    border: 1px solid var(--border-input);
    background: transparent;
    color: var(--text-muted);
    font-size: 16px;
    line-height: 1;
    cursor: pointer;
  }
  .clear:hover {
    color: var(--text);
  }
  .detail dl {
    margin: 0;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .detail dt {
    font-size: 12px;
    color: var(--text-muted);
  }
  .detail dd {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .detail dd.warn {
    color: var(--warn-text);
  }
  .eyebrow {
    font-size: 11px;
    color: var(--text-muted);
  }
  .hosts {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 13px;
  }
  .hosts li {
    display: flex;
    justify-content: space-between;
    gap: 10px;
  }
  .pick {
    display: block;
    width: calc(100% + 12px);
    padding: 4px 6px;
    margin: -4px -6px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .pick .bar-top {
    display: flex;
  }
  .pick .track,
  .pick .fill {
    display: block;
  }
  .pick:hover {
    background: var(--surface-hover);
  }
  .pick.on {
    background: var(--surface-raised);
  }
  .node-select {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-muted);
    font-size: 13px;
  }
  .layout {
    display: grid;
    grid-template-columns: minmax(0, 3fr) minmax(340px, 1fr);
    gap: 16px;
    align-items: start;
  }
  @media (max-width: 1100px) {
    .layout {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  .side {
    max-height: 760px;
    overflow: auto;
  }
  .small {
    font-size: 13px;
    margin: 0;
  }
  .tiny {
    font-size: 11px;
    margin: 0;
  }
  .bars {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .bar-top {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    font-size: 13px;
  }
  .ellipsis {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .note {
    font-size: 11px;
  }
  .val {
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }
  .track {
    margin-top: 4px;
    height: 4px;
    border-radius: 2px;
    background: var(--surface-raised);
  }
  .fill {
    height: 100%;
    border-radius: 2px;
  }
</style>

<script lang="ts">
  // Statistik eines Hosts: Kennzahlen mit Vorzeitraum, Verlauf, Abgelehnte, Herkunft, Pfade.
  import AppShell from '../lib/components/AppShell.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import HostHeader from '../lib/components/HostHeader.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import KpiCard from '../lib/components/KpiCard.svelte';
  import LineChart from '../lib/components/LineChart.svelte';
  import ColumnChart from '../lib/components/ColumnChart.svelte';
  import { api, countryName, formatBytes, LOG_REASONS, type Host, type LogReason } from '../lib/api';
  import { bucketize, fmt, SERIES, type Range } from '../lib/stats';
  import { toasts } from '../lib/toast.svelte';

  interface HourRow {
    t: string;
    requests: number;
    previous: number;
    visitors: number;
    bytes: number;
    latency: number | null;
    mtls?: number;
    waf?: number;
    ip?: number;
    other?: number;
  }

  interface HostStatsData {
    host: string;
    since: string;
    requests: { total: number; previous: number };
    visitors: { total: number; previous: number };
    bytes: { out: number; in: number; previous: number };
    latency: { median: number | null; p95: number | null; previous: number | null };
    errors: { count: number; share: number };
    compression: { share: number | null; encodings: string[] };
    hourly: HourRow[];
    denied: number;
    countries: { country: string; count: number; denied: number }[];
    unknown_country: number;
    paths: { path: string; count: number; errors: number; denied: number }[];
    top_denied_ips: { ip: string; count: number; reason: LogReason; country: string | null }[];
    source: string;
  }

  let { params = {} }: { params?: Record<string, string> } = $props();
  const hostId = $derived(Number(params.id));

  const RANGES: Range[] = ['24h', '7d', '30d'];
  const RANGE_LABEL: Record<Range, string> = { '24h': 'Vortag', '7d': 'Vorwoche', '30d': 'Vormonat' };
  let rangeIdx = $state(0);
  const range = $derived(RANGES[rangeIdx]);

  let host = $state<Host | null>(null);
  let data = $state<HostStatsData | null>(null);
  let error = $state('');
  let loading = $state(false);
  let banning = $state<string | null>(null);
  let banned = $state<Set<string>>(new Set());
  /** Kennzahl für das große Diagramm */
  let metric = $state<'requests' | 'visitors' | 'bytes'>('requests');

  $effect(() => {
    api
      .get<Host>(`/hosts/${hostId}`)
      .then((h) => (host = h))
      .catch((e) => (error = e instanceof Error ? e.message : String(e)));
  });

  $effect(() => {
    const h = host;
    const r = range;
    if (!h) return;
    loading = true;
    api
      .get<HostStatsData>(`/stats/host?domain=${encodeURIComponent(h.domain)}&range=${r}`)
      .then((d) => {
        if (range === r) {
          data = d;
          error = '';
        }
      })
      .catch((e) => (error = e instanceof Error ? e.message : String(e)))
      .finally(() => (loading = false));
  });

  const delta = (cur: number | null, prev: number | null) =>
    cur === null || prev === null || prev === 0 ? null : ((cur - prev) / prev) * 100;

  const KEYS = ['requests', 'previous', 'visitors', 'bytes', 'mtls', 'waf', 'ip', 'other'];
  const buckets = $derived(data ? bucketize(data.hourly as never, range, KEYS) : []);
  const spark = (key: string) => buckets.map((b) => b.values[key] ?? 0);
  const latencySpark = $derived(data ? data.hourly.map((h) => h.latency) : []);

  const METRIC = {
    requests: { label: 'Anfragen', format: fmt },
    visitors: { label: 'Besucher', format: fmt },
    bytes: { label: 'Daten', format: formatBytes }
  } as const;

  const lineSeries = $derived(
    metric === 'requests'
      ? [
          { key: 'requests', label: 'Anfragen', color: '#8B7CF6' },
          { key: 'previous', label: 'Vorzeitraum', color: '#8A91A0', dashed: true }
        ]
      : [{ key: metric, label: METRIC[metric].label, color: '#8B7CF6' }]
  );

  const deniedSeries = $derived(
    (['mtls', 'waf', 'ip', 'other'] as const)
      .filter((k) => data?.hourly.some((h) => (h[k] ?? 0) > 0) || k !== 'other')
      .map((k) => ({ key: k, label: SERIES[k].label, color: SERIES[k].color }))
  );

  const maxCountry = $derived(Math.max(1, ...(data?.countries.map((c) => c.count) ?? [1])));
  const maxPath = $derived(Math.max(1, ...(data?.paths.map((p) => p.count) ?? [1])));

  async function ban(ip: string) {
    banning = ip;
    try {
      await api.post('/bans', { ip, hours: 24, reason: `aus der Statistik von ${host?.domain ?? ''}`.slice(0, 250) });
      banned = new Set([...banned, ip]);
      toasts.show('ok', `${ip} ist für 24 Stunden gesperrt.`);
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      banning = null;
    }
  }

  const reasonLabel = (r: string) => LOG_REASONS[r as LogReason]?.label ?? r;
  const reasonColor = (r: string) =>
    r === 'mtls' ? SERIES.mtls.color : r === 'waf' ? SERIES.waf.color : ['ip', 'ban', 'internal'].includes(r) ? SERIES.ip.color : SERIES.other.color;
  const logsLink = (q: string) => `#/logs?q=${encodeURIComponent(q)}`;
</script>

<AppShell active="hosts">
  <HostHeader {hostId} {host} tab="stats" onChange={(h) => (host = h)} />

  <div class="toolbar">
    <span class="muted small">
      {#if data}
        Seit {new Date(data.since).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })}
        {#if data.source !== 'sqlite'} · aus {data.source === 'loki' ? 'Loki' : 'VictoriaLogs'}{/if}
      {/if}
      {#if loading} · lädt …{/if}
    </span>
    <span class="spacer"></span>
    <SegmentedControl options={['24 Stunden', '7 Tage', '30 Tage']} bind:selected={rangeIdx} groupLabel="Zeitraum" />
  </div>

  {#if error}<Alert tone="bad" title="Statistik nicht verfügbar" text={error} />{/if}

  {#if data}
    {@const d = data}
    <section class="kpis" aria-label="Kennzahlen">
      <KpiCard
        label="Anfragen"
        value={fmt(d.requests.total)}
        delta={delta(d.requests.total, d.requests.previous)}
        sub={`zum ${RANGE_LABEL[range]}`}
        spark={spark('requests')}
        selected={metric === 'requests'}
        onclick={() => (metric = 'requests')}
      />
      <KpiCard
        label="Besucher"
        value={fmt(d.visitors.total)}
        delta={delta(d.visitors.total, d.visitors.previous)}
        sub="verschiedene Adressen, ohne Bots"
        spark={spark('visitors')}
        selected={metric === 'visitors'}
        onclick={() => (metric = 'visitors')}
      />
      <KpiCard
        label="Daten ausgeliefert"
        value={formatBytes(d.bytes.out)}
        delta={delta(d.bytes.out, d.bytes.previous)}
        sub={`${formatBytes(d.bytes.in)} empfangen`}
        spark={spark('bytes')}
        selected={metric === 'bytes'}
        onclick={() => (metric = 'bytes')}
      />
      <KpiCard
        label="Antwortzeit (Median)"
        value={d.latency.median === null ? '–' : `${fmt(d.latency.median)} ms`}
        delta={delta(d.latency.median, d.latency.previous)}
        upIsBad
        sub={d.latency.p95 === null ? 'keine Anfragen' : `95 % unter ${fmt(Math.ceil(d.latency.p95))} ms`}
        spark={latencySpark}
      />
      <KpiCard
        label="Serverfehler (5xx)"
        value={`${d.errors.share.toLocaleString('de-DE', { maximumFractionDigits: 2 })} %`}
        tone={d.errors.share >= 5 ? 'bad' : d.errors.share >= 1 ? 'warn' : 'neutral'}
        sub={d.errors.count ? `${fmt(d.errors.count)} Anfragen` : 'keine Serverfehler'}
      />
      <KpiCard
        label="Komprimiert ausgeliefert"
        value={d.compression.share === null ? '–' : `${d.compression.share.toLocaleString('de-DE')} %`}
        sub={d.compression.encodings.length ? d.compression.encodings.join(' & ') : 'keine Kompression'}
      />
    </section>

    <section class="grid-main">
      <div class="card">
        <h2>{METRIC[metric].label} pro {range === '24h' ? 'Stunde' : range === '7d' ? '6 Stunden' : 'Tag'}</h2>
        <LineChart {buckets} series={lineSeries} label={`${METRIC[metric].label} im Zeitraum`} format={METRIC[metric].format} />
      </div>
      <div class="card">
        <div class="row">
          <h2>Abgelehnt</h2>
          <span class="spacer"></span>
          <span class="muted small">{fmt(d.denied)} im Zeitraum</span>
        </div>
        <ColumnChart {buckets} series={deniedSeries} label="Abgelehnte Anfragen nach Grund" />
      </div>
    </section>

    <section class="grid-lists">
      <div class="card">
        <div class="row">
          <h2>Herkunft</h2>
          <span class="spacer"></span>
          <a class="small" href="#/stats-map">Karte öffnen</a>
        </div>
        {#if d.countries.length}
          <ul class="bars">
            {#each d.countries as c (c.country)}
              <li>
                <div class="bar-top">
                  <a class="plain-link" href={`#/stats-map?country=${c.country}`}>{countryName(c.country)}</a>
                  <span class="val">
                    {#if c.denied}<span class="warn-text">{fmt(c.denied)} abgelehnt</span>{/if}
                    {fmt(c.count)}
                  </span>
                </div>
                <div class="track"><div class="fill" style:width="{(c.count / maxCountry) * 100}%"></div></div>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="muted small">Keine Länder – GeoIP fehlt oder nur lokale Adressen.</p>
        {/if}
        {#if d.unknown_country}<p class="muted tiny">{fmt(d.unknown_country)} ohne Land (private oder lokale Adressen)</p>{/if}
      </div>

      <div class="card">
        <h2>Pfade</h2>
        {#if d.paths.length}
          <ul class="bars">
            {#each d.paths as p (p.path)}
              <li>
                <div class="bar-top">
                  <a class="mono path" href={logsLink(`host:${d.host} ${p.path.replaceAll('*', '')}`)} title={p.path}>{p.path}</a>
                  <span class="val">
                    {#if p.errors}<span class="warn-text">{fmt(p.errors)} Fehler</span>{/if}
                    {#if p.denied}<span class="muted">{fmt(p.denied)} abgelehnt</span>{/if}
                    {fmt(p.count)}
                  </span>
                </div>
                <div class="track"><div class="fill" style:width="{(p.count / maxPath) * 100}%"></div></div>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="muted small">Keine Anfragen im Zeitraum.</p>
        {/if}
      </div>

      <div class="card">
        <h2>Top abgelehnte IPs</h2>
        {#if d.top_denied_ips.length}
          <ul class="ips">
            {#each d.top_denied_ips as ip (ip.ip)}
              <li>
                <i style:background={reasonColor(ip.reason)}></i>
                <div class="ip-main">
                  <a class="mono" href={logsLink(`ip:${ip.ip}`)}>{ip.ip}</a>
                  <span class="muted tiny">{reasonLabel(ip.reason)}{ip.country ? ` · ${countryName(ip.country)}` : ''}</span>
                </div>
                <span class="val">{fmt(ip.count)}</span>
                <button
                  type="button"
                  class="ban"
                  disabled={banning !== null || banned.has(ip.ip)}
                  onclick={() => ban(ip.ip)}
                >{banned.has(ip.ip) ? 'Gesperrt' : banning === ip.ip ? '…' : 'Sperren'}</button>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="muted small">Nichts abgelehnt im Zeitraum.</p>
        {/if}
      </div>
    </section>
  {:else if !error}
    <p class="muted">Lädt …</p>
  {/if}
</AppShell>

<style>
  .toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
  .spacer {
    flex: 1;
  }
  h2 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
  }
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
  }
  .grid-main {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
    gap: 14px;
  }
  .grid-lists {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    align-items: start;
  }
  @media (max-width: 1100px) {
    .grid-main,
    .grid-lists {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  .small {
    font-size: 13px;
  }
  .tiny {
    font-size: 12px;
  }
  .bars,
  .ips {
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
  .path {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text);
    text-decoration: none;
  }
  .plain-link {
    color: var(--text);
    text-decoration: none;
  }
  .plain-link:hover {
    text-decoration: underline;
  }
  .path:hover {
    text-decoration: underline;
  }
  .val {
    display: inline-flex;
    gap: 10px;
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
    font-size: 13px;
  }
  .warn-text {
    color: var(--warn-text);
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
    background: #8b7cf6;
  }
  .ips li {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .ips i {
    width: 8px;
    height: 8px;
    border-radius: 2px;
    flex-shrink: 0;
  }
  .ip-main {
    display: flex;
    flex-direction: column;
    min-width: 0;
    flex: 1;
  }
  .ip-main a {
    font-size: 13px;
    color: var(--text);
    text-decoration: none;
  }
  .ip-main .tiny {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .ban {
    padding: 4px 10px;
    border-radius: var(--radius);
    border: 1px solid var(--border-input);
    background: transparent;
    color: var(--text-muted);
    font: inherit;
    font-size: 12px;
    cursor: pointer;
  }
  .ban:hover:not(:disabled) {
    color: var(--text);
  }
  .ban:disabled {
    cursor: default;
    opacity: 0.6;
  }
</style>

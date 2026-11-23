<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import StatsTabs from '../lib/components/StatsTabs.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import LineChart from '../lib/components/LineChart.svelte';
  import KpiCard from '../lib/components/KpiCard.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import { api, formatBytes, type NodeInfo } from '../lib/api';
  import { bucketize, compact, fmt, type Bucket, type Range } from '../lib/stats';

  interface Kpi {
    requests: number;
    requests_prev?: number;
    visitors?: number;
    visitors_prev?: number;
    bytes_out?: number;
    bytes_out_prev?: number;
    bytes_in?: number;
    latency?: number | null;
    latency_prev?: number | null;
    latency_p95?: number | null;
    errors?: number;
    errors_share?: number;
    errors_top_host?: string | null;
    compressed_share?: number | null;
    encodings?: string[];
  }

  interface Mix {
    status: Record<string, number>;
    proto: Record<string, number>;
    clients: Record<string, number>;
  }

  interface PathRow {
    host: string;
    path: string;
    count: number;
    errors: number;
    client_errors: number;
  }

  interface Traffic {
    range: string;
    kpi: Kpi;
    since?: string | null;
    days?: number;
    series?: { t: string; requests?: number; previous?: number; visitors?: number; bytes?: number; latency?: number; errors?: number }[];
    months?: { t: string; requests: number; bytes: number; errors: number }[];
    days_series?: { t: string; requests: number; bytes: number; errors: number }[];
    mix?: Mix;
    clients?: { name: string; kind: 'browser' | 'app' | 'bot'; count: number }[];
    status_codes?: { code: string; text: string; count: number }[];
    paths_top?: PathRow[];
    paths_errors?: PathRow[];
    hosts?: {
      host: string;
      requests: number;
      bytes: number;
      median_ms: number | null;
      p95_ms: number | null;
      errors: number;
      denied: number;
      availability: number | null;
    }[];
  }

  const RANGES = ['24h', '7d', '30d', 'all'] as const;
  const RANGE_TEXT = ['zum Vortag', 'zur Vorwoche', 'zum Vormonat', ''];
  let range = $state(0);
  let node = $state('');
  let nodes = $state<NodeInfo[]>([]);
  let data = $state<Traffic | null>(null);
  let error = $state('');
  let loading = $state(false);
  let metric = $state<'requests' | 'visitors' | 'bytes' | 'latency'>('requests');
  let pathTab = $state(0);

  async function load() {
    loading = true;
    try {
      data = await api.get<Traffic>(`/stats/traffic?range=${RANGES[range]}&node=${encodeURIComponent(node)}`);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }
  load();
  api.get<NodeInfo[]>('/nodes').then((n) => (nodes = n.filter((x) => x.state !== 'pending')));

  const isAll = $derived(RANGES[range] === 'all');
  const k = $derived(data?.kpi);
  const delta = (cur: number | null | undefined, prev: number | null | undefined) =>
    cur == null || prev == null || prev === 0 ? null : ((cur - prev) / prev) * 100;

  const KEYS = ['requests', 'previous', 'visitors', 'bytes', 'errors'];
  const hourBuckets = $derived(data?.series && !isAll ? bucketize(data.series as never, RANGES[range] as Range, KEYS) : []);
  const latencyHourly = $derived((data?.series ?? []).map((s) => s.latency ?? null));

  /** Gesamter Zeitraum: Monate – bei weniger als drei Monaten Aufzeichnung Tage */
  const byDay = $derived((data?.months?.length ?? 0) < 3);
  const monthBuckets = $derived.by((): Bucket[] =>
    byDay
      ? (data?.days_series ?? []).map((m) => {
          const d = new Date(`${m.t}T00:00:00`);
          return {
            start: d,
            label: d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }),
            title: d.toLocaleDateString('de-DE', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' }),
            values: { requests: m.requests, bytes: m.bytes, errors: m.errors }
          };
        })
      : (data?.months ?? []).map((m) => {
      const d = new Date(`${m.t}-01T00:00:00`);
      return {
        start: d,
        label: d.toLocaleDateString('de-DE', { month: 'short', year: '2-digit' }),
        title: d.toLocaleDateString('de-DE', { month: 'long', year: 'numeric' }),
            values: { requests: m.requests, bytes: m.bytes, errors: m.errors }
          };
        })
  );

  const chartMetric = $derived(isAll && (metric === 'visitors' || metric === 'latency') ? 'requests' : metric);
  const METRIC = {
    requests: { label: 'Anfragen', format: fmt },
    visitors: { label: 'Besucher', format: fmt },
    bytes: { label: 'Daten', format: formatBytes },
    latency: { label: 'Antwortzeit (Median)', format: (n: number) => `${n.toLocaleString('de-DE')} ms` }
  } as const;

  // Antwortzeit je Bucket: Median der Stundenwerte im Bucket
  const latencyBuckets = $derived.by((): Bucket[] => {
    if (!data?.series || isAll) return [];
    const r = RANGES[range] as Range;
    const base = bucketize([], r, ['latency']);
    const groups = base.map(() => [] as number[]);
    const idx = new Map(base.map((b, i) => [b.start.getTime(), i]));
    const step = r === '24h' ? 3600e3 : r === '7d' ? 6 * 3600e3 : 24 * 3600e3;
    for (const s of data.series) {
      if (s.latency == null) continue;
      const t = new Date(s.t).getTime();
      for (const [start, i] of idx) {
        if (t >= start && t < start + step) {
          groups[i].push(s.latency);
          break;
        }
      }
    }
    return base.map((b, i) => {
      const g = groups[i].sort((a, x) => a - x);
      return { ...b, values: { latency: g.length ? g[Math.floor(g.length / 2)] : 0 } };
    });
  });

  const chartBuckets = $derived(isAll ? monthBuckets : chartMetric === 'latency' ? latencyBuckets : hourBuckets);
  const chartSeries = $derived(
    chartMetric === 'requests' && !isAll
      ? [
          { key: 'requests', label: 'Anfragen', color: '#8B7CF6' },
          { key: 'previous', label: 'Vorzeitraum', color: '#8A91A0', dashed: true }
        ]
      : [{ key: chartMetric, label: METRIC[chartMetric].label, color: '#8B7CF6' }]
  );
  const unit = $derived(isAll ? (byDay ? 'Tag' : 'Monat') : range === 0 ? 'Stunde' : range === 1 ? '6 Stunden' : 'Tag');

  const spark = (key: string) => hourBuckets.map((b) => b.values[key] ?? 0);
  const monthSpark = (key: 'requests' | 'bytes' | 'errors') => monthBuckets.map((b) => b.values[key] ?? 0);

  const MIX_ROWS: { group: string; key: keyof Mix; items: [string, string][] }[] = [
    { group: 'Statuscodes', key: 'status', items: [['2', '2xx erfolgreich'], ['3', '3xx weiterg.'], ['4', '4xx abgelehnt'], ['5', '5xx Fehler']] },
    { group: 'Protokoll', key: 'proto', items: [['3', 'HTTP/3'], ['2', 'HTTP/2'], ['1.1', 'HTTP/1.1']] },
    { group: 'Clients', key: 'clients', items: [['browser', 'Browser'], ['app', 'Apps & API'], ['bot', 'Bots/Crawler']] }
  ];
  const KIND_LABEL = { browser: 'Browser', app: 'App', bot: 'Bot' } as const;
  const pct = (v: number | undefined) => `${(v ?? 0).toLocaleString('de-DE', { maximumFractionDigits: 1 })} %`;

  const paths = $derived(pathTab === 0 ? (data?.paths_top ?? []) : (data?.paths_errors ?? []));
  const maxPath = $derived(Math.max(1, ...paths.map((p) => (pathTab === 0 ? p.count : p.errors + p.client_errors))));
  const maxClient = $derived(Math.max(1, ...(data?.clients ?? []).map((c) => c.count)));
  const maxCode = $derived(Math.max(1, ...(data?.status_codes ?? []).map((c) => c.count)));
  const short = (h: string) => h.split('.')[0];
  const ms = (v: number | null) => (v === null ? '–' : `${v.toLocaleString('de-DE')} ms`);
  const sinceText = $derived(
    data?.since ? new Date(`${data.since}T00:00:00`).toLocaleDateString('de-DE', { month: 'long', year: 'numeric' }) : ''
  );
</script>

<AppShell active="stats">
  <PageHeader title="Statistik" subtitle="Wie viel durch die Nodes geht und wie schnell die Dienste antworten." />
  <StatsTabs current="#/stats-traffic" />

  <div class="row">
    <SegmentedControl
      groupLabel="Zeitraum"
      options={['Letzte 24 Stunden', '7 Tage', '30 Tage', 'Gesamter Zeitraum']}
      bind:selected={range}
      onChange={load}
    />
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

  {#if data && k}
    <div class="kpis">
      <KpiCard
        label="Anfragen"
        value={compact(k.requests)}
        delta={isAll ? null : delta(k.requests, k.requests_prev)}
        sub={isAll ? (sinceText ? `seit ${sinceText}` : 'seit Beginn der Aufzeichnung') : RANGE_TEXT[range]}
        spark={isAll ? monthSpark('requests') : spark('requests')}
        selected={metric === 'requests'}
        onclick={() => (metric = 'requests')}
      />
      <KpiCard
        label="Besucher"
        value={fmt(k.visitors ?? 0)}
        delta={isAll ? null : delta(k.visitors, k.visitors_prev)}
        sub="verschiedene Adressen, ohne Bots"
        spark={isAll ? [] : spark('visitors')}
        selected={metric === 'visitors' && !isAll}
        onclick={isAll ? undefined : () => (metric = 'visitors')}
      />
      <KpiCard
        label="Daten ausgeliefert"
        value={formatBytes(k.bytes_out ?? 0)}
        delta={isAll ? null : delta(k.bytes_out, k.bytes_out_prev)}
        sub={`${formatBytes(k.bytes_in ?? 0)} empfangen`}
        spark={isAll ? monthSpark('bytes') : spark('bytes')}
        selected={metric === 'bytes'}
        onclick={() => (metric = 'bytes')}
      />
      <KpiCard
        label="Antwortzeit (Median)"
        value={k.latency == null ? '–' : `${fmt(k.latency)} ms`}
        delta={isAll ? null : delta(k.latency, k.latency_prev)}
        upIsBad
        sub={k.latency_p95 == null ? (isAll ? 'Median der Tageswerte' : 'keine Anfragen') : `95 % unter ${fmt(Math.ceil(k.latency_p95))} ms`}
        spark={isAll ? [] : latencyHourly}
        selected={metric === 'latency' && !isAll}
        onclick={isAll ? undefined : () => (metric = 'latency')}
      />
      <KpiCard
        label="Serverfehler (5xx)"
        value={pct(k.errors_share)}
        tone={(k.errors_share ?? 0) >= 5 ? 'bad' : (k.errors_share ?? 0) >= 1 ? 'warn' : 'neutral'}
        sub={k.errors ? `${fmt(k.errors)} Anfragen${k.errors_top_host ? ` · meist ${short(k.errors_top_host)}` : ''}` : 'keine Serverfehler'}
        spark={isAll ? monthSpark('errors') : spark('errors')}
        sparkColor="#D95926"
      />
      <KpiCard
        label="Komprimiert ausgeliefert"
        value={k.compressed_share == null ? '–' : pct(k.compressed_share)}
        sub={k.encodings?.length ? k.encodings.join(' & ') : 'Anteil der 200-Antworten'}
      />
    </div>

    <div class="main-grid">
      <section class="card" aria-labelledby="req-title">
        <h2 id="req-title">{METRIC[chartMetric].label} pro {unit}</h2>
        {#if chartBuckets.length}
          <LineChart buckets={chartBuckets} series={chartSeries} height={240} label={`${METRIC[chartMetric].label} pro ${unit}`} format={METRIC[chartMetric].format} />
        {:else}
          <p class="muted small">Noch keine Daten.</p>
        {/if}
        {#if isAll}
          <p class="muted small">
            Aus den Tageswerten, die Tesseract dauerhaft aufhebt – auch wenn die Einzeleinträge nach der Aufbewahrungszeit gelöscht sind.
            {#if data.days}{fmt(data.days)} Tage erfasst.{/if}
          </p>
        {/if}
      </section>

      {#if data.mix}
        <section class="card" aria-labelledby="mix-title">
          <h2 id="mix-title">Zusammensetzung</h2>
          {#each MIX_ROWS as g (g.group)}
            <div class="mix-group">
              <span class="eyebrow">{g.group}</span>
              {#each g.items as [key, label] (key)}
                {@const v = data.mix[g.key][key] ?? 0}
                <div class="mix-row">
                  <span class="mix-label">{label}</span>
                  <span class="mix-track"><span class="mix-fill" style:width="{v}%"></span></span>
                  <span class="mix-val">{pct(v)}</span>
                </div>
              {/each}
            </div>
          {/each}
        </section>
      {/if}
    </div>

    <div class="lists">
      {#if !isAll}
        <section class="card" aria-labelledby="paths-title">
          <div class="row">
            <h2 id="paths-title">Pfade</h2>
            <span class="spacer"></span>
            <SegmentedControl groupLabel="Pfade" options={['Aufgerufen', 'Mit Fehler']} bind:selected={pathTab} />
          </div>
          {#if paths.length}
            <ul class="bars">
              {#each paths as p (p.host + p.path)}
                {@const v = pathTab === 0 ? p.count : p.errors + p.client_errors}
                <li>
                  <div class="bar-top">
                    <a class="mono path" href={`#/logs?q=${encodeURIComponent(`host:${p.host} ${p.path.replaceAll('*', '')}`)}`} title={`${p.host}${p.path}`}
                      >{p.path} <span class="muted host">{short(p.host)}</span></a
                    >
                    <span class="val">
                      {#if p.errors}<span class="warn-text">{fmt(p.errors)} Fehler</span>{/if}
                      {#if pathTab === 1 && p.client_errors}<span class="muted">{fmt(p.client_errors)} × 4xx</span>{/if}
                      {compact(v)}
                    </span>
                  </div>
                  <div class="track"><div class="fill" style:width="{(v / maxPath) * 100}%"></div></div>
                </li>
              {/each}
            </ul>
          {:else}
            <p class="muted small">{pathTab === 0 ? 'Keine Anfragen im Zeitraum.' : 'Keine Fehler im Zeitraum.'}</p>
          {/if}
        </section>
      {/if}

      <section class="card" aria-labelledby="clients-title">
        <h2 id="clients-title">Browser, Apps und Bots</h2>
        {#if data.clients?.length}
          <ul class="bars">
            {#each data.clients as c (c.name + c.kind)}
              <li>
                <div class="bar-top">
                  <span>{c.name} <span class="muted kind">{KIND_LABEL[c.kind]}</span></span>
                  <span class="val">{compact(c.count)}</span>
                </div>
                <div class="track"><div class="fill {c.kind}" style:width="{(c.count / maxClient) * 100}%"></div></div>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="muted small">Keine Anfragen im Zeitraum.</p>
        {/if}
      </section>

      <section class="card" aria-labelledby="codes-title">
        <h2 id="codes-title">Statuscodes</h2>
        {#if data.status_codes?.length}
          <ul class="bars">
            {#each data.status_codes as c (c.code)}
              <li>
                <div class="bar-top">
                  <span><span class="mono">{c.code}</span> <span class="muted">{c.text}</span></span>
                  <span class="val">{compact(c.count)}</span>
                </div>
                <div class="track"><div class="fill s{c.code[0]}" style:width="{(c.count / maxCode) * 100}%"></div></div>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="muted small">Keine Anfragen im Zeitraum.</p>
        {/if}
      </section>
    </div>

    {#if data.hosts}
      <section class="card" aria-labelledby="hosts-title">
        <h2 id="hosts-title">Hosts im Vergleich</h2>
        <p class="muted small">Antwortzeit = Zeit bis zur Antwort des Dienstes, gemessen am Node (nur durchgelassene Anfragen).</p>
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th scope="col">Host</th>
                <th scope="col" class="num">Anfragen</th>
                <th scope="col" class="num">Daten raus</th>
                <th scope="col" class="num">Median</th>
                <th scope="col" class="num">95 % schneller als</th>
                <th scope="col" class="num">Fehler (5xx)</th>
                <th scope="col" class="num">Erreichbar</th>
              </tr>
            </thead>
            <tbody>
              {#each data.hosts as h (h.host)}
                <tr>
                  <td><a href={`#/logs?q=${encodeURIComponent('host:' + h.host)}`}>{h.host}</a></td>
                  <td class="num">{fmt(h.requests)}{#if h.denied} <span class="muted small">({fmt(h.denied)} abgelehnt)</span>{/if}</td>
                  <td class="num">{formatBytes(h.bytes)}</td>
                  <td class="num">{ms(h.median_ms)}</td>
                  <td class="num">{ms(h.p95_ms)}</td>
                  <td class="num" class:bad={h.errors > 0}>
                    {#if h.errors}<a href={`#/logs?q=${encodeURIComponent(`host:${h.host} status:5xx`)}`}>{fmt(h.errors)}</a>{:else}0{/if}
                  </td>
                  <td class="num" class:bad={h.availability !== null && h.availability < 99}>
                    {h.availability === null ? '–' : `${h.availability.toLocaleString('de-DE')} %`}
                  </td>
                </tr>
              {:else}
                <tr><td colspan="7" class="muted">Keine Anfragen im Zeitraum.</td></tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {/if}
  {/if}
</AppShell>

<style>
  .node-select {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-muted);
    font-size: 13px;
  }
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
  }
  .main-grid {
    display: grid;
    grid-template-columns: minmax(0, 2.4fr) minmax(260px, 1fr);
    gap: 16px;
    align-items: start;
  }
  .lists {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 16px;
    align-items: start;
  }
  @media (max-width: 1100px) {
    .main-grid {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  h2 {
    margin: 0;
  }
  .small {
    font-size: 13px;
    margin: 0;
  }
  .mix-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .eyebrow {
    font-size: 11px;
    color: var(--text-muted);
  }
  .mix-row {
    display: grid;
    grid-template-columns: 110px minmax(0, 1fr) 52px;
    align-items: center;
    gap: 10px;
    font-size: 13px;
  }
  .mix-track {
    height: 6px;
    border-radius: 3px;
    background: var(--surface-raised);
    overflow: hidden;
  }
  .mix-fill {
    display: block;
    height: 100%;
    background: #8b7cf6;
    border-radius: 3px;
  }
  .mix-val {
    text-align: right;
    font-variant-numeric: tabular-nums;
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
  .path {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text);
    text-decoration: none;
  }
  .path:hover {
    text-decoration: underline;
  }
  .host,
  .kind {
    font-family: var(--font-sans);
    font-size: 11px;
  }
  .val {
    display: inline-flex;
    gap: 10px;
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
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
  .fill.bot {
    background: #8a91a0;
  }
  .fill.browser {
    background: #3987e5;
  }
  .fill.s4 {
    background: #c98500;
  }
  .fill.s5 {
    background: #d95926;
  }
  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .bad,
  .bad a {
    color: var(--bad-text);
  }
</style>

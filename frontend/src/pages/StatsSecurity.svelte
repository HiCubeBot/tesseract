<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import StatsTabs from '../lib/components/StatsTabs.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import ColumnChart from '../lib/components/ColumnChart.svelte';
  import BarList from '../lib/components/BarList.svelte';
  import WorldMap from '../lib/components/WorldMap.svelte';
  import StatCard from '../lib/components/StatCard.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import { api, countryName, LOG_REASONS, type LogReason, type NodeInfo } from '../lib/api';
  import { bucketize, fmt, SERIES, type Range } from '../lib/stats';

  interface Security {
    total: number;
    denied: number;
    waf_blocked: number;
    hourly: { t: string; mtls?: number; waf?: number; ip?: number; other?: number }[];
    top_ips: { ip: string; count: number; country: string | null; reason: LogReason }[];
    countries: { country: string; count: number }[];
    attacks: { name: string; count: number }[];
    top_rules: { rule: number; count: number }[];
    by_host: { host: string; total: number; mtls: number; waf: number; ip: number; other: number }[];
    geoip: boolean;
  }

  const RANGES: Range[] = ['24h', '7d', '30d'];
  let range = $state(0);
  let node = $state('');
  let nodes = $state<NodeInfo[]>([]);
  let data = $state<Security | null>(null);
  let error = $state('');

  async function load() {
    try {
      data = await api.get<Security>(`/stats/security?range=${RANGES[range]}&node=${encodeURIComponent(node)}`);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();
  api.get<NodeInfo[]>('/nodes').then((n) => (nodes = n.filter((x) => x.state !== 'pending')));

  const series = Object.entries(SERIES).map(([key, s]) => ({ key, ...s }));
  const buckets = $derived(data ? bucketize(data.hourly, RANGES[range], series.map((s) => s.key)) : []);
  const share = $derived(data && data.total ? Math.round((100 * data.denied) / data.total) : 0);
  const rangeText = $derived(['in 24 Stunden', 'in 7 Tagen', 'in 30 Tagen'][range]);
  const privateOnlyCert = $derived(
    data?.by_host.filter((h) => h.total > 10 && h.mtls / h.total > 0.9).map((h) => h.host.split('.')[0]) ?? []
  );
</script>

<AppShell active="stats">
  <PageHeader title="Statistik" subtitle="Was abgewehrt wird – aus den Logs aller Nodes." />
  <StatsTabs current="#/stats" />

  <div class="row">
    <SegmentedControl groupLabel="Zeitraum" options={['Letzte 24 Stunden', '7 Tage', '30 Tage']} bind:selected={range} onChange={load} />
    <label class="node-select">
      <span>Node</span>
      <select class="input" bind:value={node} onchange={load}>
        <option value="">Alle Nodes</option>
        {#each nodes as n (n.id)}<option value={n.name}>{n.name}</option>{/each}
      </select>
    </label>
  </div>

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if data}
    <div class="stats">
      <StatCard label="Anfragen" value={fmt(data.total)} sub={rangeText} tone="neutral" />
      <StatCard label="Abgelehnt" value={fmt(data.denied)} sub={`${share} % aller Anfragen`} tone={data.denied ? 'warn' : 'ok'} />
      <StatCard label="Von Coraza blockiert" value={fmt(data.waf_blocked)} sub={data.attacks[0] ? `meist ${data.attacks[0].name}` : 'keine Angriffe'} tone="ok" />
    </div>

    <section class="card" aria-labelledby="denied-title">
      <h2 id="denied-title">Abgelehnt pro {range === 0 ? 'Stunde' : range === 1 ? '6 Stunden' : 'Tag'}</h2>
      <ColumnChart {buckets} {series} label="Abgelehnte Anfragen nach Grund" />
    </section>

    <section class="card" aria-labelledby="geo-title">
      <h2 id="geo-title">Herkunft abgelehnter Anfragen</h2>
      {#if data.geoip}
        {#if data.countries.length}
          <div class="geo">
            <WorldMap items={data.countries} label="Weltkarte: abgelehnte Anfragen nach Herkunftsland" />
            <BarList color="#9085E9" items={data.countries.slice(0, 8).map((c) => ({ label: countryName(c.country), value: c.count }))} />
          </div>
        {:else}
          <p class="muted small">Keine abgelehnten Anfragen mit bekanntem Land im Zeitraum (private und lokale Adressen haben kein Land).</p>
        {/if}
      {:else}
        <p class="muted small">
          Für die Karte eine lokale GeoIP-Datenbank (.mmdb) hinterlegen: <span class="mono">TESSERACT_GEOIP_DB</span> –
          Bezug siehe docs/deployment.md › GeoIP. Es geht keine Anfrage nach außen.
        </p>
      {/if}
    </section>

    <div class="cols">
      <section class="card" aria-labelledby="ips-title">
        <h2 id="ips-title">Top abgelehnte IPs</h2>
        <BarList
          color="#CF7D45"
          items={data.top_ips.map((i) => ({
            label: i.ip,
            value: i.count,
            mono: true,
            href: `#/logs?q=${encodeURIComponent('ip:' + i.ip)}`,
            note: [i.country ? countryName(i.country) : '', LOG_REASONS[i.reason]?.label].filter(Boolean).join(' · ')
          }))}
        />
      </section>

    </div>

    <div class="cols">
      <section class="card" aria-labelledby="attack-title">
        <div class="row">
          <h2 id="attack-title">Coraza · Angriffsarten</h2>
          <span class="spacer"></span>
          <a class="small" href="#/logs?q=reason:waf">Treffer in den Logs ansehen</a>
        </div>
        <BarList color="#14A399" items={data.attacks.map((a) => ({ label: a.name, value: a.count }))} empty="Keine blockierten Angriffe im Zeitraum." />
        {#if data.top_rules.length}
          <p class="muted small">
            Häufigste Regeln:
            {#each data.top_rules.slice(0, 5) as r, i (r.rule)}{i ? ', ' : ''}<a class="mono" href={`#/logs?q=rule:${r.rule}`}>{r.rule}</a> ({fmt(r.count)}){/each}
          </p>
        {/if}
      </section>

      <section class="card" aria-labelledby="host-title">
        <h2 id="host-title">Am meisten abgelehnt · nach Host</h2>
        {#if data.by_host.length}
          <ul class="hosts">
            {#each data.by_host as h (h.host)}
              <li>
                <div class="row-top">
                  <a href={`#/logs?q=${encodeURIComponent('host:' + h.host)}&filter=denied`}>{h.host}</a>
                  <span>{fmt(h.total)}</span>
                </div>
                <div class="stack" role="img" aria-label={`${h.host}: ${h.mtls} ohne Zertifikat, ${h.waf} WAF, ${h.ip} IP-Filter, ${h.other} sonstige`}>
                  {#each series as s (s.key)}
                    {@const v = h[s.key as 'mtls' | 'waf' | 'ip' | 'other']}
                    {#if v}<span style:flex-grow={v} style:background={s.color} title={`${s.label}: ${fmt(v)}`}></span>{/if}
                  {/each}
                </div>
              </li>
            {/each}
          </ul>
          {#if privateOnlyCert.length}
            <p class="muted small">{privateOnlyCert.join(', ')}: fast nur am fehlenden Zertifikat abgewiesen – der private Dienst wirkt.</p>
          {/if}
        {:else}
          <p class="muted small">Nichts abgelehnt im Zeitraum.</p>
        {/if}
      </section>
    </div>
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
  .stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 14px;
  }
  .cols {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 16px;
    align-items: start;
  }
  .geo {
    display: grid;
    grid-template-columns: minmax(0, 3fr) minmax(220px, 1fr);
    gap: 20px;
    align-items: start;
  }
  @media (max-width: 900px) {
    .geo {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  .small {
    font-size: 13px;
    margin: 0;
    line-height: 1.5;
  }
  .hosts {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .row-top {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
  }
  .stack {
    margin-top: 5px;
    display: flex;
    gap: 2px;
    height: 8px;
  }
  .stack span {
    flex-basis: 0;
    min-width: 2px;
  }
  .stack span:last-child {
    border-radius: 0 4px 4px 0;
  }
</style>

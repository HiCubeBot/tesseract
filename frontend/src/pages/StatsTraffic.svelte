<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import StatsTabs from '../lib/components/StatsTabs.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import ColumnChart from '../lib/components/ColumnChart.svelte';
  import StatCard from '../lib/components/StatCard.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import { api, formatBytes, type NodeInfo } from '../lib/api';
  import { bucketize, fmt, type Range } from '../lib/stats';

  interface Traffic {
    total: number;
    bytes: number;
    hourly: { t: string; ok?: number; redirect?: number; client?: number; server?: number; denied?: number }[];
    composition: Record<string, number>;
    hosts: {
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

  const RANGES: Range[] = ['24h', '7d', '30d'];
  let range = $state(0);
  let node = $state('');
  let nodes = $state<NodeInfo[]>([]);
  let data = $state<Traffic | null>(null);
  let error = $state('');

  async function load() {
    try {
      data = await api.get<Traffic>(`/stats/traffic?range=${RANGES[range]}&node=${encodeURIComponent(node)}`);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();
  api.get<NodeInfo[]>('/nodes').then((n) => (nodes = n.filter((x) => x.state !== 'pending')));

  // Feste Reihenfolge der Kategorien (Farbe folgt der Kategorie, nie dem Rang);
  // gegen die dunkle Fläche geprüft (Helligkeit, Farbsehschwäche, Kontrast)
  const series = [
    { key: 'ok', label: '2xx erfolgreich', color: '#3987E5' },
    { key: 'redirect', label: '3xx Umleitung', color: '#C98500' },
    { key: 'client', label: '4xx Client-Fehler', color: '#199E70' },
    { key: 'server', label: '5xx Server-Fehler', color: '#D95926' },
    { key: 'denied', label: 'abgelehnt', color: '#9085E9' }
  ];
  const buckets = $derived(data ? bucketize(data.hourly, RANGES[range], series.map((s) => s.key)) : []);
  const errors = $derived(data?.composition.server ?? 0);
  const ms = (v: number | null) => (v === null ? '–' : `${v.toLocaleString('de-DE')} ms`);
  const peak = $derived.by(() => {
    if (!buckets.length) return null;
    const totals = buckets.map((b) => Object.values(b.values).reduce((a, x) => a + x, 0));
    const i = totals.indexOf(Math.max(...totals));
    return totals[i] ? buckets[i].title : null;
  });
</script>

<AppShell active="stats">
  <PageHeader title="Statistik" subtitle="Wie viel durch die Nodes geht und wie schnell die Dienste antworten." />
  <StatsTabs current="#/stats-traffic" />

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
      <StatCard label="Anfragen" value={fmt(data.total)} sub={peak ? `Spitze: ${peak}` : 'noch keine'} tone="neutral" />
      <StatCard label="Daten raus" value={formatBytes(data.bytes)} sub="Antworten an Clients" tone="neutral" />
      <StatCard
        label="Server-Fehler (5xx)"
        value={fmt(errors)}
        sub={errors ? 'Dienste prüfen – siehe Tabelle' : 'keine'}
        tone={errors ? 'bad' : 'ok'}
        subTone={errors ? 'bad' : 'muted'}
      />
    </div>

    <section class="card" aria-labelledby="req-title">
      <h2 id="req-title">Anfragen pro {range === 0 ? 'Stunde' : range === 1 ? '6 Stunden' : 'Tag'}</h2>
      <ColumnChart {buckets} {series} label="Anfragen nach Ergebnis" />
    </section>

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
  .small {
    font-size: 13px;
    margin: 0;
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

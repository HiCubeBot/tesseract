<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import { session } from '../lib/session.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import StatsTabs from '../lib/components/StatsTabs.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import ColumnChart from '../lib/components/ColumnChart.svelte';
  import BarList from '../lib/components/BarList.svelte';
  import WorldMap from '../lib/components/WorldMap.svelte';
  import KpiCard from '../lib/components/KpiCard.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import { api, countryName, LOG_REASONS, type LogReason, type NodeInfo } from '../lib/api';
  import { bucketize, fmt, SERIES, type Range } from '../lib/stats';
  import { toasts } from '../lib/toast.svelte';

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
    geoip_attribution: string | null;
    previous: { total: number; denied: number };
    waf_detected: number;
    login_failed: number;
    hourly_all: { t: string; total: number; denied: number; mtls?: number; waf?: number; ip?: number; login_failed?: number }[];
    top_ips_flagged: {
      ip: string;
      count: number;
      reason: LogReason;
      country: string | null;
      city: string | null;
      own: boolean;
      internal: boolean;
    }[];
  }

  const RANGES: Range[] = ['24h', '7d', '30d'];
  let range = $state(0);
  let node = $state('');
  let nodes = $state<NodeInfo[]>([]);
  let data = $state<Security | null>(null);
  let error = $state('');

  // Karte: alle Anfragen, nur abgelehnte oder nur angenommene
  const WHICH = ['all', 'denied', 'allowed'] as const;
  const WHICH_LABELS = ['Alle', 'Abgelehnt', 'Angenommen'];
  const WHICH_COLORS = ['#3987E5', '#D95926', '#199E70'];
  let which = $state(0);
  let geo = $state<{ countries: { country: string; count: number }[]; unknown: number } | null>(null);

  async function loadGeo() {
    try {
      geo = await api.get(
        `/stats/countries?range=${RANGES[range]}&node=${encodeURIComponent(node)}&which=${WHICH[which]}`
      );
    } catch {
      geo = null;
    }
  }

  async function load() {
    try {
      data = await api.get<Security>(`/stats/security?range=${RANGES[range]}&node=${encodeURIComponent(node)}`);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
    loadGeo();
  }
  load();
  api.get<NodeInfo[]>('/nodes').then((n) => (nodes = n.filter((x) => x.state !== 'pending')));

  const series = Object.entries(SERIES).map(([key, s]) => ({ key, ...s }));
  const buckets = $derived(data ? bucketize(data.hourly, RANGES[range], series.map((s) => s.key)) : []);
  const share = $derived(data && data.total ? Math.round((100 * data.denied) / data.total) : 0);
  const rangeText = $derived(['in 24 Stunden', 'in 7 Tagen', 'in 30 Tagen'][range]);
  // Verlaufslinien der Kennzahlen
  const kpiBuckets = $derived(
    data ? bucketize(data.hourly_all, RANGES[range], ['total', 'denied', 'mtls', 'waf', 'ip', 'login_failed']) : []
  );
  const spark = (k: string) => kpiBuckets.map((b) => b.values[k] ?? 0);
  const sumOf = (k: 'mtls' | 'waf' | 'ip') => (data ? data.hourly_all.reduce((s, h) => s + (h[k] ?? 0), 0) : 0);
  const delta = (cur: number, prev: number) => (prev ? ((cur - prev) / prev) * 100 : null);

  // Top-IPs: eigene (Geräte mit Zertifikat, eigene Sitzung) und interne wahlweise ausblenden
  let hideOwn = $state(false);
  const topIps = $derived((data?.top_ips_flagged ?? []).filter((i) => !hideOwn || !(i.own || i.internal)).slice(0, 8));
  let banned = $state<Set<string>>(new Set());
  let banning = $state<string | null>(null);
  async function ban(ip: string) {
    banning = ip;
    try {
      await api.post('/bans', { ip, hours: 24, reason: 'aus der Statistik' });
      banned = new Set([...banned, ip]);
      toasts.show('ok', `${ip} ist für 24 Stunden gesperrt.`);
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      banning = null;
    }
  }
  const reasonColor = (r: string) =>
    r === 'mtls'
      ? SERIES.mtls.color
      : r === 'waf'
        ? SERIES.waf.color
        : ['ip', 'ban', 'internal'].includes(r)
          ? SERIES.ip.color
          : SERIES.other.color;

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
    <div class="kpis">
      <KpiCard label="Anfragen" value={fmt(data.total)} delta={delta(data.total, data.previous.total)} sub={rangeText} spark={spark('total')} sparkColor="#8A91A0" />
      <KpiCard
        label="Abgelehnt gesamt"
        value={fmt(data.denied)}
        delta={delta(data.denied, data.previous.denied)}
        upIsBad
        sub={`${share} % aller Anfragen`}
        spark={spark('denied')}
        sparkColor="#8A91A0"
      />
      <KpiCard label="Ohne Zertifikat" value={fmt(sumOf('mtls'))} sub="mTLS-Handshake abgelehnt" spark={spark('mtls')} sparkColor={SERIES.mtls.color} />
      <KpiCard
        label="Von Coraza blockiert"
        value={fmt(data.waf_blocked)}
        sub={data.waf_detected ? `${fmt(data.waf_detected)} nur erkannt` : data.attacks[0] ? `meist ${data.attacks[0].name}` : 'keine Angriffe'}
        spark={spark('waf')}
        sparkColor={SERIES.waf.color}
      />
      <KpiCard label="Vom IP-Filter" value={fmt(sumOf('ip'))} sub="eigene Einträge, Listen, Sperren" spark={spark('ip')} sparkColor={SERIES.ip.color} />
      <KpiCard
        label="Fehlanmeldungen"
        value={fmt(data.login_failed)}
        tone={data.login_failed >= 10 ? 'warn' : 'neutral'}
        sub={data.login_failed ? 'an der Oberfläche' : 'keine am Controller'}
        spark={spark('login_failed')}
        sparkColor="#E5A443"
      />
    </div>

    <div class="main-grid">
      <section class="card" aria-labelledby="denied-title">
        <div class="row">
          <h2 id="denied-title">Abgelehnt pro {range === 0 ? 'Stunde' : range === 1 ? '6 Stunden' : 'Tag'}</h2>
          <span class="spacer"></span>
          {#if data.waf_detected}<span class="muted small">{fmt(data.waf_detected)} nur erkannt (WAF protokolliert)</span>{/if}
        </div>
        <ColumnChart {buckets} {series} label="Abgelehnte Anfragen nach Grund" height={220} />
      </section>

      <section class="card" aria-labelledby="ips-title">
        <div class="row">
          <h2 id="ips-title">Top abgelehnte IPs</h2>
          <span class="spacer"></span>
          <label class="check small"><input type="checkbox" bind:checked={hideOwn} /> Eigene ausblenden</label>
        </div>
        {#if topIps.length}
          <ul class="ips">
            {#each topIps as i (i.ip)}
              <li>
                <i style:background={reasonColor(i.reason)}></i>
                <div class="ip-main">
                  <span class="ip-line">
                    <a class="mono" href={`#/logs?q=${encodeURIComponent('ip:' + i.ip)}`}>{i.ip}</a>
                    {#if i.own}<span class="badge" title="Diese Adresse nutzt auch ein freigegebenes Gerät oder deine Sitzung">eigene</span>{/if}
                    {#if i.internal}<span class="badge" title="Aus einem der internen Netze">intern</span>{/if}
                  </span>
                  <span class="muted tiny ellipsis">
                    {[LOG_REASONS[i.reason]?.label, i.city, i.country ? countryName(i.country) : ''].filter(Boolean).join(' · ')}
                  </span>
                </div>
                <span class="num">{fmt(i.count)}</span>
                {#if i.own || i.internal}
                  <a class="act" href={`#/logs?q=${encodeURIComponent('ip:' + i.ip)}&filter=denied`} title="Welche Dienste wurden abgelehnt?">Wohin?</a>
                {:else if session.isAdmin}
                  <button type="button" class="act" disabled={banning !== null || banned.has(i.ip)} onclick={() => ban(i.ip)}>
                    {banned.has(i.ip) ? 'Gesperrt' : 'Sperren'}
                  </button>
                {/if}
              </li>
            {/each}
          </ul>
        {:else}
          <p class="muted small">Nichts abgelehnt im Zeitraum.</p>
        {/if}
      </section>
    </div>

    <section class="card" aria-labelledby="geo-title">
      <div class="row geo-head">
        <h2 id="geo-title">Herkunft der Anfragen</h2>
        <a class="small" href="#/stats-map">Karte öffnen</a>
        <span class="spacer"></span>
        {#if data.geoip}
          <SegmentedControl groupLabel="Welche Anfragen" options={WHICH_LABELS} bind:selected={which} onChange={loadGeo} />
        {/if}
      </div>
      {#if data.geoip}
        <!-- Karte immer zeigen, sobald GeoIP da ist – auch leer, damit klar ist, dass alles bereit ist -->
        {@const items = geo?.countries ?? []}
        <div class="geo">
          <WorldMap
            {items}
            color={WHICH_COLORS[which]}
            label={`Weltkarte: ${WHICH_LABELS[which].toLowerCase()} Anfragen nach Herkunftsland`}
          />
          <BarList
            color={WHICH_COLORS[which]}
            items={items.slice(0, 8).map((c) => ({ label: countryName(c.country), value: c.count, href: `#/stats-map?country=${c.country}` }))}
            empty={`Keine ${which === 1 ? 'abgelehnten' : which === 2 ? 'angenommenen' : ''} Anfragen mit bekanntem Land im Zeitraum. Private und lokale Adressen (z. B. 127.0.0.1, 192.168.…) haben kein Land.`}
          />
        </div>
        {#if geo?.unknown}
          <p class="muted tiny">{fmt(geo.unknown)} weitere ohne Land (private oder lokale Adressen)</p>
        {/if}
        {#if data.geoip_attribution}
          <p class="muted tiny"><a href="https://db-ip.com" rel="noopener noreferrer" target="_blank">{data.geoip_attribution}</a></p>
        {/if}
      {:else}
        <p class="muted small">
          Für die Karte eine GeoIP-Datenbank hinterlegen: automatisch mit <span class="mono">TESSERACT_GEOIP_AUTO=dbip</span> (holt DB-IP Lite
          monatlich selbst) oder als Datei mit <span class="mono">TESSERACT_GEOIP_DB</span> – siehe docs/deployment.md › GeoIP.
        </p>
      {/if}
    </section>

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
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
  }
  .main-grid {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr);
    gap: 16px;
    align-items: start;
  }
  @media (max-width: 1100px) {
    .main-grid {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  .check {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--text-muted);
    cursor: pointer;
  }
  .ips {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
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
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  .ip-line {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
  }
  .ip-line a {
    color: var(--text);
    text-decoration: none;
  }
  .badge {
    padding: 0 6px;
    border-radius: 999px;
    font-size: 11px;
    line-height: 18px;
    background: var(--surface-raised);
    color: var(--text-muted);
  }
  .ellipsis {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .num {
    font-variant-numeric: tabular-nums;
    font-size: 13px;
  }
  .act {
    min-width: 72px;
    text-align: center;
    padding: 4px 10px;
    border-radius: var(--radius);
    border: 1px solid var(--border-input);
    background: transparent;
    color: var(--text-muted);
    font: inherit;
    font-size: 12px;
    cursor: pointer;
    text-decoration: none;
  }
  .act:hover:not(:disabled) {
    color: var(--text);
  }
  .act:disabled {
    opacity: 0.6;
    cursor: default;
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
  .tiny {
    margin: 0;
    font-size: 11px;
  }
  .main-grid h2,
  .geo-head h2 {
    margin: 0;
  }
</style>

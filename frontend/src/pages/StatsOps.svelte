<script lang="ts">
  // Statistik › Betrieb: Summen seit Beginn, Erreichbarkeit der Nodes und Hosts (Uptime-Monitor),
  // Zertifikate, Rekorde und Vorfälle.
  import { onDestroy } from 'svelte';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import StatsTabs from '../lib/components/StatsTabs.svelte';
  import UptimeBars from '../lib/components/UptimeBars.svelte';
  import KpiCard from '../lib/components/KpiCard.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import { api, formatAgo, formatBytes } from '../lib/api';
  import { compact, fmt } from '../lib/stats';

  interface Day {
    day: string;
    checks: number;
    pct: number | null;
    down_minutes: number;
    outages: number;
  }
  interface Row {
    status: 'up' | 'down' | 'unknown';
    since: string | null;
    error: string | null;
    ms: number | null;
    days: Day[];
    pct: number | null;
    outages: number;
    down_minutes: number;
  }
  interface Monitor {
    days: string[];
    nodes: (Row & { name: string; location: string })[];
    hosts: (Row & { id: number; domain: string; node: string; public: boolean; name: string })[];
    incidents: { kind: string; ref: string; started_at: string; ended_at: string | null; minutes: number; error: string | null }[];
  }
  interface Ops {
    requests: number;
    bytes_out: number;
    denied: number;
    first_day: string | null;
    days: number;
    per_day_requests: number;
    per_day_bytes: number;
    status_url: string;
    status_hosts: number;
    status_enabled: boolean;
    records: {
      day?: { day: string; requests: number; host: string };
      hour?: { hour: string; requests: number; host: string | null };
      bytes_day?: { day: string; bytes: number };
      denied_hour?: { hour: string; denied: number; host: string | null };
      fastest?: { host: string; median_ms: number };
      slowest?: { host: string; median_ms: number };
    };
  }
  interface Cert {
    names: string[];
    not_before: string;
    not_after: string;
    days_left: number;
    status: 'ok' | 'soon' | 'expired';
  }

  let mon = $state<Monitor | null>(null);
  let ops = $state<Ops | null>(null);
  let certs = $state<Cert[] | null>(null);
  let certErrors = $state(0);
  let error = $state('');
  let showAll = $state(false);

  async function load() {
    try {
      [mon, ops] = await Promise.all([api.get<Monitor>('/monitor'), api.get<Ops>('/stats/operations')]);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();
  const timer = setInterval(load, 60_000);
  onDestroy(() => clearInterval(timer));
  api
    .get<{ certificates: Cert[]; errors: unknown[] }>('/certificates')
    .then((r) => {
      certs = r.certificates;
      certErrors = r.errors?.length ?? 0;
    })
    .catch(() => (certs = []));

  const monthAgo = Date.now() - 30 * 864e5;
  const renewed = $derived((certs ?? []).filter((c) => new Date(c.not_before).getTime() >= monthAgo));
  const expiring = $derived([...(certs ?? [])].sort((a, b) => a.days_left - b.days_left).slice(0, 5));
  const hosts = $derived(showAll ? (mon?.hosts ?? []) : (mon?.hosts ?? []).slice(0, 8));
  const downNow = $derived((mon?.hosts ?? []).filter((h) => h.status === 'down').length);

  const pct = (v: number | null) => (v === null ? '–' : `${v.toLocaleString('de-DE', { maximumFractionDigits: 1 })} %`);
  const dayText = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const hourText = (h: string) => {
    const d = new Date(h);
    return `${d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })}, ${d.getHours()}–${d.getHours() + 1} Uhr`;
  };
  const short = (h: string | null | undefined) => (h ? h.split('.')[0] : '?');
  function summary(r: Row): string {
    if (r.status === 'down') return `nicht erreichbar seit ${formatAgo(r.since)}${r.error ? ` · ${r.error}` : ''}`;
    if (r.status === 'unknown') return r.error ?? 'noch nicht geprüft';
    if (!r.outages) return 'kein Ausfall';
    return `${r.outages} Ausfall${r.outages > 1 ? 'e' : ''} (${r.down_minutes} Min.)`;
  }
</script>

<AppShell active="stats">
  <PageHeader title="Statistik" subtitle="Läuft alles? Erreichbarkeit, Zertifikate und Rekorde." />
  <StatsTabs current="#/stats-ops" />

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if ops}
    <div class="kpis">
      <KpiCard
        label={ops.first_day ? `Anfragen seit ${new Date(`${ops.first_day}T00:00:00`).toLocaleDateString('de-DE', { month: 'long', year: 'numeric' })}` : 'Anfragen'}
        value={compact(ops.requests)}
        sub={`Ø ${fmt(ops.per_day_requests)} am Tag`}
      />
      <KpiCard label="Daten ausgeliefert" value={formatBytes(ops.bytes_out)} sub={`Ø ${formatBytes(ops.per_day_bytes)} am Tag`} />
      <KpiCard
        label="Abgelehnt"
        value={fmt(ops.denied)}
        sub={ops.requests ? `${((100 * ops.denied) / ops.requests).toLocaleString('de-DE', { maximumFractionDigits: 2 })} % aller Anfragen` : '–'}
      />
      <KpiCard
        label="Beobachtet seit"
        value={`${fmt(ops.days)} ${ops.days === 1 ? 'Tag' : 'Tagen'}`}
        sub={ops.first_day ? `erster Tag: ${dayText(ops.first_day)}` : 'noch keine Tageswerte'}
      />
    </div>
  {/if}

  {#if mon}
    <div class="grid">
      <div class="col">
      <section class="card" aria-labelledby="nodes-title">
        <div class="row">
          <h2 id="nodes-title">Erreichbarkeit der Nodes</h2>
          <span class="spacer"></span>
          <span class="muted small">Verbindung zum Controller · letzte 30 Tage</span>
        </div>
        <ul class="rows">
          {#each mon.nodes as n (n.name)}
            <li>
              <div class="who">
                <span class="mono name">{n.name}</span>
                <span class="small sub" class:bad={n.status === 'down'}>
                  <i class="dot {n.status}"></i>{n.status === 'down' ? 'getrennt' : n.status === 'up' ? 'verbunden' : 'unbekannt'} · {summary(n)}
                </span>
              </div>
              <UptimeBars days={n.days} label={`Erreichbarkeit ${n.name} je Tag`} />
              <span class="pct">{pct(n.pct)}</span>
            </li>
          {/each}
        </ul>
        {@render legend()}
      </section>

      <section class="card" aria-labelledby="hosts-title">
        <div class="row">
          <h2 id="hosts-title">Erreichbarkeit der Hosts</h2>
          <span class="spacer"></span>
          <span class="muted small">Dienst antwortet nicht oder Node getrennt · letzte 30 Tage</span>
        </div>
        {#if downNow}<Alert tone="bad" title={`${downNow} ${downNow === 1 ? 'Dienst' : 'Dienste'} gerade nicht erreichbar`} />{/if}
        <ul class="rows">
          {#each hosts as h (h.domain)}
            <li>
              <div class="who">
                <a class="mono name" href={`#/hosts/${h.id}`}>{h.domain}</a>
                <span class="small sub" class:bad={h.status === 'down'}><i class="dot {h.status}"></i>{summary(h)}</span>
              </div>
              <UptimeBars days={h.days} label={`Erreichbarkeit ${h.domain} je Tag`} />
              <span class="pct">{pct(h.pct)}</span>
            </li>
          {:else}
            <li class="muted small">Keine überwachten Hosts. Die Überwachung lässt sich je Host unter „Allgemein“ einschalten.</li>
          {/each}
        </ul>
        {#if mon.hosts.length > 8}
          <button type="button" class="link" onclick={() => (showAll = !showAll)}>
            {showAll ? 'Weniger anzeigen' : `Alle ${mon.hosts.length} Hosts anzeigen`}
          </button>
        {/if}
        {@render legend()}
      </section>

      </div>
      <div class="col">
      <section class="card" aria-labelledby="certs-title">
        <div class="row">
          <h2 id="certs-title">Zertifikate</h2>
          <span class="spacer"></span>
          <span class="muted small">letzte 30 Tage</span>
        </div>
        {#if certs === null}
          <p class="muted small">Lädt …</p>
        {:else}
          <div class="cert-kpi">
            <span class="big">{renewed.length}</span>
            <span class="muted">{renewed.length === 1 ? 'Erneuerung' : 'Erneuerungen'}</span>
            {#if certErrors}<span class="warn-pill">⚠ {certErrors} Node{certErrors > 1 ? 's' : ''} nicht geprüft</span>{/if}
          </div>
          <span class="eyebrow">Nächste Abläufe</span>
          <ul class="certs">
            {#each expiring as c (c.names.join() + c.not_after)}
              <li>
                <span class="mono ellipsis" title={c.names.join(', ')}>{c.names[0]}</span>
                <span class="muted">{dayText(c.not_after.slice(0, 10))}</span>
                <span class:warn-text={c.status !== 'ok'}>in {c.days_left} Tagen</span>
              </li>
            {:else}
              <li class="muted">Keine Zertifikate gefunden.</li>
            {/each}
          </ul>
          <a class="small" href="#/certificates">Alle Zertifikate</a>
        {/if}
      </section>

      {#if ops}
        {@const r = ops.records}
        <section class="card" aria-labelledby="rec-title">
          <div class="row">
            <h2 id="rec-title">Rekorde</h2>
            <span class="spacer"></span>
            <span class="muted small">seit Beginn der Aufzeichnung</span>
          </div>
          <dl class="records">
            {#if r.day}<div><dt>Stärkster Tag<small>{dayText(r.day.day)} · meist {short(r.day.host)}</small></dt><dd>{compact(r.day.requests)}<small>Anfragen</small></dd></div>{/if}
            {#if r.hour}<div><dt>Stärkste Stunde<small>{hourText(r.hour.hour)} · meist {short(r.hour.host)}</small></dt><dd>{fmt(r.hour.requests)}<small>Anfragen</small></dd></div>{/if}
            {#if r.bytes_day}<div><dt>Meiste Daten an einem Tag<small>{dayText(r.bytes_day.day)}</small></dt><dd>{formatBytes(r.bytes_day.bytes)}<small>ausgeliefert</small></dd></div>{/if}
            {#if r.denied_hour}<div><dt>Größte Abweisungs-Welle<small>{hourText(r.denied_hour.hour)} · meist {short(r.denied_hour.host)}</small></dt><dd>{fmt(r.denied_hour.denied)}<small>abgelehnt in 1 Std.</small></dd></div>{/if}
            {#if r.fastest}<div><dt>Schnellster Host<small>{r.fastest.host} · letzte 30 Tage</small></dt><dd>{fmt(r.fastest.median_ms)} ms<small>Median</small></dd></div>{/if}
            {#if r.slowest}<div><dt>Langsamster Host<small>{r.slowest.host} · letzte 30 Tage</small></dt><dd>{fmt(r.slowest.median_ms)} ms<small>Median</small></dd></div>{/if}
          </dl>
          {#if !r.day}<p class="muted small">Rekorde gibt es ab dem ersten vollständigen Tag.</p>{/if}
        </section>
      {/if}
      </div>
    </div>

    <div class="grid">
      <section class="card" aria-labelledby="inc-title">
        <h2 id="inc-title">Letzte Ausfälle</h2>
        {#if mon.incidents.length}
          <ul class="incidents">
            {#each mon.incidents as i (i.kind + i.ref + i.started_at)}
              <li>
                <i class="dot {i.ended_at ? 'up' : 'down'}"></i>
                <span class="mono">{i.ref}</span>
                <span class="muted small">{i.kind === 'node' ? 'Node' : 'Host'} · {new Date(i.started_at).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })} · {i.ended_at ? `${i.minutes} Min.` : 'dauert an'}{i.error ? ` · ${i.error}` : ''}</span>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="muted small">Bisher kein Ausfall erkannt.</p>
        {/if}
      </section>

      {#if ops}
        <section class="card" aria-labelledby="status-title">
          <h2 id="status-title">Öffentliche Statusseite</h2>
          {#if !ops.status_enabled}
            <p class="muted small">
              Ausgeschaltet. Unter <a href="#/settings">Einstellungen › Allgemein</a> einschalten{ops.status_hosts
                ? ` – ${ops.status_hosts} ${ops.status_hosts === 1 ? 'Dienst ist' : 'Dienste sind'} schon dafür ausgewählt`
                : ''}.
            </p>
          {:else if ops.status_hosts}
            <p class="small">
              {ops.status_hosts} {ops.status_hosts === 1 ? 'Dienst steht' : 'Dienste stehen'} auf der Statusseite – ohne Anmeldung erreichbar, auch wenn die Oberfläche
              nur aus bestimmten Netzen geht.
            </p>
            <a class="small mono" href={ops.status_url} target="_blank" rel="noopener">{ops.status_url}</a>
          {:else}
            <p class="muted small">
              Noch kein Dienst freigegeben. Je Host unter „Allgemein › Überwachung“ „Auf der öffentlichen Statusseite zeigen“ wählen. Die Seite zeigt nur den Namen und die
              Erreichbarkeit, keine Domains oder Adressen.
            </p>
          {/if}
        </section>
      {/if}
    </div>
  {:else if !error}
    <p class="muted">Lädt …</p>
  {/if}
</AppShell>

{#snippet legend()}
  <div class="legend">
    <span><i class="sq ok"></i>ohne Ausfall</span>
    <span><i class="sq warn"></i>unter 30 Min.</span>
    <span><i class="sq bad"></i>ab 30 Min.</span>
    <span><i class="sq none"></i>keine Daten</span>
  </div>
{/snippet}

<style>
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
  }
  .grid {
    display: grid;
    grid-template-columns: minmax(0, 2.2fr) minmax(300px, 1fr);
    gap: 16px;
    align-items: start;
  }
  @media (max-width: 1100px) {
    .grid {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  h2 {
    margin: 0;
  }
  .col {
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-width: 0;
  }
  .small {
    font-size: 13px;
    margin: 0;
  }
  .rows,
  .certs,
  .incidents {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .rows li {
    display: grid;
    grid-template-columns: minmax(140px, 220px) minmax(0, 1fr) 64px;
    align-items: center;
    gap: 14px;
  }
  .who {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .name {
    font-size: 13px;
    color: var(--text);
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .sub {
    font-size: 12px;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .sub.bad {
    color: var(--bad-text);
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
    display: inline-block;
    background: var(--text-muted);
  }
  .dot.up {
    background: #2f9e6b;
  }
  .dot.down {
    background: #d9604a;
  }
  .pct {
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-size: 13px;
  }
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    font-size: 12px;
    color: var(--text-muted);
  }
  .legend span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .sq {
    width: 9px;
    height: 9px;
    border-radius: 2px;
    background: var(--surface-raised);
  }
  .sq.ok {
    background: #2f9e6b;
  }
  .sq.warn {
    background: #d9a23a;
  }
  .sq.bad {
    background: #d9604a;
  }
  .cert-kpi {
    display: flex;
    align-items: baseline;
    gap: 8px;
    flex-wrap: wrap;
  }
  .big {
    font-size: 26px;
    font-weight: 600;
  }
  .warn-pill {
    margin-left: auto;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
    color: var(--warn-text);
    background: rgba(229, 164, 67, 0.14);
  }
  .eyebrow {
    font-size: 11px;
    color: var(--text-muted);
  }
  .certs li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    gap: 10px;
    font-size: 13px;
  }
  .ellipsis {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .warn-text {
    color: var(--warn-text);
  }
  .records {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .records div {
    display: flex;
    justify-content: space-between;
    gap: 10px;
  }
  .records dt,
  .records dd {
    margin: 0;
    display: flex;
    flex-direction: column;
    font-size: 14px;
  }
  .records dd {
    text-align: right;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .records small {
    font-size: 11px;
    font-weight: 400;
    color: var(--text-muted);
  }
  .incidents li {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    flex-wrap: wrap;
  }
  .link {
    align-self: flex-start;
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent-text);
    font: inherit;
    font-size: 13px;
    cursor: pointer;
  }
  .bad {
    color: var(--bad-text);
  }
</style>

<script lang="ts">
  import { onDestroy } from 'svelte';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import KpiCard from '../lib/components/KpiCard.svelte';
  import LineChart from '../lib/components/LineChart.svelte';
  import Sparkline from '../lib/components/Sparkline.svelte';
  import EventItem from '../lib/components/EventItem.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import Button from '../lib/components/Button.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import BansCard from '../lib/components/BansCard.svelte';
  import {
    api,
    formatAgo,
    formatAgoShort,
    formatDay,
    ACTION_LABELS,
    type AuditEntry,
    type Host,
    type CertificateOverview,
    type Invite,
    type NodeInfo
  } from '../lib/api';
  import { applyNode } from '../lib/nodes';
  import { bucketize, compact, fmt, SERIES } from '../lib/stats';
  import { counts } from '../lib/counts.svelte';

  interface Security {
    total: number;
    denied: number;
    previous: { total: number; denied: number };
    hourly_all: { t: string; total: number; denied: number; mtls?: number; waf?: number; ip?: number }[];
    geoip: boolean;
  }
  interface MonitorHost {
    id: number;
    domain: string;
    status: 'up' | 'down' | 'unknown';
    since: string | null;
    error: string | null;
    pct: number | null;
  }

  let hosts = $state<Host[]>([]);
  let nodes = $state<NodeInfo[]>([]);
  let events = $state<AuditEntry[]>([]);
  let invites = $state<Invite[]>([]);
  let certs = $state<CertificateOverview | null>(null);
  let sec = $state<Security | null>(null);
  let activity = $state<Record<string, { total: number; hourly: number[] }>>({});
  let monitor = $state<MonitorHost[]>([]);
  let error = $state('');
  let applying = $state<number | null>(null);

  // Zertifikate separat laden – das Auslesen kann ein paar Sekunden dauern
  api.get<CertificateOverview>('/certificates').then(
    (c) => (certs = c),
    () => (certs = null)
  );
  const expiring = $derived((certs?.certificates ?? []).filter((c) => c.source !== 'lokal' && c.days_left < 30).slice(0, 5));

  async function load() {
    try {
      [hosts, nodes, events, invites] = await Promise.all([
        api.get<Host[]>('/hosts'),
        api.get<NodeInfo[]>('/nodes'),
        api.get<AuditEntry[]>('/audit?limit=8'),
        api.get<Invite[]>('/invites')
      ]);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
    // Statistik und Monitor: Fehler bleiben still – die Übersicht soll trotzdem stehen
    api.get<Security>('/stats/security?range=24h').then((s) => (sec = s), () => {});
    api
      .get<{ hosts: Record<string, { total: number; hourly: number[] }> }>('/stats/activity')
      .then((a) => (activity = a.hosts), () => {});
    api.get<{ hosts: MonitorHost[] }>('/monitor?days=1').then((m) => (monitor = m.hosts), () => {});
    counts.refresh();
  }
  load();
  const timer = setInterval(load, 60_000);
  onDestroy(() => clearInterval(timer));

  async function apply(node: NodeInfo) {
    applying = node.id;
    try {
      await applyNode(node);
    } finally {
      applying = null;
      await load();
    }
  }

  const live = $derived(hosts.filter((h) => h.enabled && !h.draft));
  const drafts = $derived(hosts.filter((h) => h.draft).length);
  const joinedNodes = $derived(nodes.filter((n) => n.state !== 'pending'));
  const onlineNodes = $derived(joinedNodes.filter((n) => n.state !== 'offline'));
  const outOfSync = $derived(joinedNodes.filter((n) => !n.in_sync || n.drift || n.state === 'offline'));
  const joinRequests = $derived(nodes.filter((n) => n.join_state === 'pending'));
  const down = $derived(monitor.filter((m) => m.status === 'down'));
  const pending = $derived(
    invites.flatMap((i) =>
      i.enrollments.filter((e) => e.status === 'pending').map((e) => ({ ...e, person: i.person_name, personId: i.person_id }))
    )
  );

  function nodeProblem(n: NodeInfo): { title: string; text: string } {
    if (n.state === 'offline')
      return { title: `${n.name} ist offline`, text: `Letzter Kontakt ${formatAgo(n.last_seen_at)}. Caddy läuft dort mit dem letzten Stand weiter.` };
    if (n.drift) return { title: `${n.name} wurde lokal geändert`, text: 'Die laufende Config weicht vom Stand des Controllers ab.' };
    return {
      title: `${n.name} ist nicht auf dem Stand des Controllers`,
      text: n.last_apply_error ?? (n.kind === 'agent' ? 'Der Agent hat die neue Config noch nicht geladen.' : 'Die Config wurde noch nicht übertragen.')
    };
  }
  const NODE_PILL = {
    online: { tone: 'ok', label: 'online' },
    drift: { tone: 'warn', label: 'lokal geändert' },
    offline: { tone: 'bad', label: 'offline' },
    error: { tone: 'bad', label: 'Fehler' },
    pending: { tone: 'neutral', label: 'wartet auf Beitritt' }
  } as const;

  // Verlauf der letzten 24 Stunden
  const buckets = $derived(sec ? bucketize(sec.hourly_all, '24h', ['total', 'denied']) : []);
  const spark = (k: string) => buckets.map((b) => b.values[k] ?? 0);
  const delta = (cur: number, prev: number) => (prev ? ((cur - prev) / prev) * 100 : null);

  // Dienste: nicht erreichbare zuerst, dann nach Anfragen der letzten 24 h
  const monState = $derived(new Map(monitor.map((m) => [m.domain, m])));
  const services = $derived(
    [...live]
      .sort((a, b) => {
        const da = monState.get(a.domain)?.status === 'down' ? 1 : 0;
        const db = monState.get(b.domain)?.status === 'down' ? 1 : 0;
        return db - da || (activity[b.domain]?.total ?? 0) - (activity[a.domain]?.total ?? 0) || a.domain.localeCompare(b.domain);
      })
      .slice(0, 8)
  );

  const allGood = $derived(!error && !down.length && !outOfSync.length && !expiring.some((c) => c.days_left < 7));

  const tone = (action: string) =>
    action.endsWith('failed') || action === 'host_down' ? 'bad' : action.startsWith('host_') ? 'mtls' : 'neutral';
</script>

<AppShell active="main">
  <PageHeader
    title="Übersicht"
    subtitle={`${joinedNodes.length} Node${joinedNodes.length === 1 ? '' : 's'} · ${live.length} aktive Hosts${drafts ? ` · ${drafts} Entwürfe` : ''}`}
    primaryLabel="Host anlegen"
    primaryHref="#/hosts/new"
  />

  {#if error}<Alert tone="bad" title="Daten konnten nicht geladen werden" text={error} />{/if}

  {#each pending as e (e.id)}
    <Alert
      tone="info"
      title={`${e.person} möchte „${e.device_name}“ registrieren`}
      text="Bestätigungscode war korrekt. Gib das Gerät frei oder lehne ab."
      actionLabel="Ansehen"
      actionHref={`#/users/${e.personId}`}
    />
  {/each}

  {#each joinRequests as node (node.id)}
    <Alert tone="info" title={`Agent möchte als „${node.name}“ beitreten`} text="Schlüssel-Fingerabdruck vergleichen und den Node bestätigen." actionLabel="Ansehen" actionHref="#/nodes" />
  {/each}

  {#each down as m (m.domain)}
    <Alert
      tone="bad"
      title={`${m.domain} ist nicht erreichbar`}
      text={`Seit ${formatAgo(m.since)}${m.error ? ` – ${m.error}` : ''}.`}
      actionLabel="Host öffnen"
      actionHref={`#/hosts/${m.id}`}
    />
  {/each}

  {#each outOfSync as node (node.id)}
    {@const p = nodeProblem(node)}
    <Alert tone={node.state === 'offline' ? 'bad' : 'warn'} title={p.title} text={p.text} actionLabel="Nodes" actionHref="#/nodes" />
  {/each}

  {#if allGood && hosts.length}
    <div class="ok-banner" role="status"><span class="dot"></span>Alles läuft – alle Nodes synchron, keine Ausfälle.</div>
  {/if}

  <div class="kpis">
    <KpiCard
      label="Anfragen · 24 h"
      value={sec ? compact(sec.total) : '–'}
      delta={sec ? delta(sec.total, sec.previous.total) : null}
      sub="zum Vortag"
      spark={spark('total')}
      onclick={() => (location.hash = '#/stats-traffic')}
    />
    <KpiCard
      label="Abgelehnt · 24 h"
      value={sec ? fmt(sec.denied) : '–'}
      delta={sec ? delta(sec.denied, sec.previous.denied) : null}
      upIsBad
      sub={sec && sec.total ? `${Math.round((100 * sec.denied) / sec.total)} % aller Anfragen` : 'keine Anfragen'}
      spark={spark('denied')}
      sparkColor={SERIES.ip.color}
      onclick={() => (location.hash = '#/stats')}
    />
    <KpiCard
      label="Aktive Hosts"
      value={String(live.length)}
      tone={down.length ? 'bad' : 'neutral'}
      sub={down.length ? `${down.length} nicht erreichbar` : monitor.some((m) => m.status === 'up') ? 'alle erreichbar' : drafts ? `${drafts} Entwürfe` : 'alle übertragen'}
      onclick={() => (location.hash = '#/hosts')}
    />
    <KpiCard
      label="Nodes online"
      value={`${onlineNodes.length}/${joinedNodes.length}`}
      tone={outOfSync.length ? 'warn' : 'neutral'}
      sub={outOfSync.length ? `${outOfSync.length} mit Abweichung` : 'alle synchron'}
      onclick={() => (location.hash = '#/nodes')}
    />
    <KpiCard
      label="Freigegebene Geräte"
      value={counts.value ? fmt(counts.value.devices) : '–'}
      sub={counts.value ? `${fmt(counts.value.persons)} Personen` : ''}
      onclick={() => (location.hash = '#/devices')}
    />
    <KpiCard
      label="Zertifikate"
      value={certs ? String(expiring.length) : '–'}
      tone={expiring.some((c) => c.days_left < 7) ? 'bad' : expiring.length ? 'warn' : 'neutral'}
      sub={certs ? (expiring.length ? 'laufen in 30 Tagen ab' : 'keins läuft bald ab') : 'prüfe …'}
      onclick={() => (location.hash = '#/certificates')}
    />
  </div>

  <div class="main">
    <section class="card" aria-labelledby="traffic-title">
      <div class="row">
        <h2 id="traffic-title">Verkehr der letzten 24 Stunden</h2>
        <span class="spacer"></span>
        <a class="small" href="#/stats-traffic">Statistik</a>
      </div>
      {#if buckets.length}
        <LineChart
          {buckets}
          height={210}
          label="Anfragen und abgelehnte Anfragen der letzten 24 Stunden"
          series={[
            { key: 'total', label: 'Anfragen', color: '#8B7CF6' },
            { key: 'denied', label: 'Abgelehnt', color: SERIES.ip.color }
          ]}
        />
      {:else}
        <p class="muted small">Noch keine Logs – sobald Anfragen über Caddy laufen, erscheinen sie hier.</p>
      {/if}
    </section>

    <section class="card" aria-labelledby="services-title">
      <div class="row">
        <h2 id="services-title">Dienste</h2>
        <span class="spacer"></span>
        <a class="small" href="#/stats-ops">Erreichbarkeit</a>
      </div>
      {#if services.length}
        <ul class="services">
          {#each services as h (h.id)}
            {@const m = monState.get(h.domain)}
            {@const a = activity[h.domain]}
            <li>
              <i class="dot {m?.status ?? 'unknown'}" title={m ? { up: 'erreichbar', down: 'nicht erreichbar', unknown: 'noch nicht geprüft' }[m.status] : 'nicht überwacht'}></i>
              <a class="mono name" href={`#/hosts/${h.id}/stats`}>{h.domain}</a>
              {#if a}<Sparkline values={a.hourly} width={72} height={20} />{/if}
              <span class="num">{a ? compact(a.total) : '0'}</span>
            </li>
          {/each}
        </ul>
        {#if live.length > services.length}<a class="small" href="#/hosts">Alle {live.length} Hosts</a>{/if}
      {:else}
        <p class="muted small">Noch keine aktiven Hosts. <a href="#/hosts/new">Host anlegen</a></p>
      {/if}
    </section>
  </div>

  <div class="cols">
    <section class="card" aria-labelledby="nodes-title">
      <div class="row">
        <h2 id="nodes-title">Nodes</h2>
        <span class="spacer"></span>
        <a class="small" href="#/nodes">Alle Nodes</a>
      </div>
      {#each nodes as node (node.id)}
        <div class="node">
          <div class="node-head">
            <span class="mono strong">{node.name}</span>
            {#if node.state === 'online' && !node.in_sync}
              <StatusPill tone="warn" label="nicht synchron" />
            {:else}
              <StatusPill tone={NODE_PILL[node.state].tone} label={NODE_PILL[node.state].label} />
            {/if}
          </div>
          <span class="muted small">
            {node.location || '–'} · {node.hosts} Hosts · zuletzt übertragen {formatAgo(node.last_applied_at)}
          </span>
          {#if node.state !== 'pending' && (!node.in_sync || node.drift || node.last_apply_error)}
            <div>
              <Button
                variant="secondary"
                size="sm"
                icon="refresh"
                label={applying === node.id ? 'Überträgt …' : 'Config erneut übertragen'}
                disabled={applying !== null}
                onClick={() => apply(node)}
              />
            </div>
          {/if}
        </div>
      {/each}
    </section>

    <section class="card" aria-labelledby="certs-title">
      <div class="row">
        <h2 id="certs-title" class="card-title">Bald ablaufende Zertifikate</h2>
        <span class="spacer"></span>
        <a href="#/certificates" class="small">Alle Zertifikate</a>
      </div>
      {#if !certs}
        <p class="muted small">Prüfe …</p>
      {:else if expiring.length}
        <ul class="plain">
          {#each expiring as c (c.fingerprint)}
            <li>
              <span class="mono">{c.names[0]}</span>
              <span class="spacer"></span>
              <StatusPill tone={c.status === 'ok' ? 'warn' : 'bad'} label={`${c.days_left} Tage · ${formatDay(c.not_after)}`} />
            </li>
          {/each}
        </ul>
      {:else}
        <p class="muted small">Keine öffentlichen Zertifikate, die in den nächsten 30 Tagen ablaufen.</p>
      {/if}
    </section>

    <BansCard compact />

    <section class="card" aria-labelledby="events-title">
      <div class="row">
        <h2 id="events-title" class="card-title">Letzte Ereignisse</h2>
        <span class="spacer"></span>
        <a href="#/audit" class="small">Audit-Log</a>
      </div>
      {#each events as e (e.id)}
        <EventItem
          time={formatAgoShort(e.created_at)}
          title={`${ACTION_LABELS[e.action] ?? e.action}${e.target ? ' · ' + e.target : ''}`}
          detail={e.actor + (e.ip ? ' · ' + e.ip : '')}
          tone={tone(e.action)}
        />
      {:else}
        <p class="muted">Noch keine Ereignisse.</p>
      {/each}
    </section>
  </div>
</AppShell>

<style>
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
  }
  .main {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
    gap: 16px;
    align-items: start;
  }
  @media (max-width: 1100px) {
    .main {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  .cols {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 16px;
    align-items: start;
  }
  h2 {
    margin: 0;
  }
  .ok-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border-radius: var(--radius-lg);
    border: 1px solid rgba(47, 158, 107, 0.4);
    background: rgba(47, 158, 107, 0.08);
    color: var(--ok-text);
    font-size: 14px;
    font-weight: 500;
  }
  .ok-banner .dot {
    background: #2f9e6b;
  }
  .services {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .services li {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    display: inline-block;
    background: var(--surface-active);
  }
  .dot.up {
    background: #2f9e6b;
  }
  .dot.down {
    background: #d9604a;
  }
  .name {
    flex: 1;
    min-width: 0;
    font-size: 13px;
    color: var(--text);
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .name:hover {
    text-decoration: underline;
  }
  .num {
    min-width: 44px;
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-size: 13px;
  }
  .node {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
  }
  .node-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .strong {
    font-weight: 600;
  }
  .small {
    font-size: 13px;
  }
  .plain {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .plain li {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    border-top: 1px solid var(--border);
  }
</style>

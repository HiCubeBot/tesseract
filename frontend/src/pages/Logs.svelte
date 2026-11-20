<script lang="ts">
  import { onDestroy } from 'svelte';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import StatsTabs from '../lib/components/StatsTabs.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import Button from '../lib/components/Button.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import {
    api,
    countryName,
    formatAgo,
    formatBytes,
    LOG_REASONS,
    type LogDetail,
    type LogEntry,
    type LogPage,
    type LogSource
  } from '../lib/api';
  import { toasts } from '../lib/toast.svelte';

  const FILTERS = ['all', 'denied', 'mtls', 'waf', 'ip'] as const;
  // Links aus der Statistik: #/logs?q=…&filter=…
  const hashParams = new URLSearchParams(location.hash.split('?')[1] ?? '');

  let entries = $state<LogEntry[]>([]);
  let sources = $state<LogSource[]>([]);
  let geoip = $state(false);
  let store = $state<'local' | 'loki' | 'victorialogs'>('local');
  let filter = $state(Math.max(0, FILTERS.indexOf((hashParams.get('filter') ?? 'all') as (typeof FILTERS)[number])));
  const initialQuery = hashParams.get('q') ?? '';
  let query = $state(initialQuery);
  let applied = $state(initialQuery);
  let node = $state('');
  let live = $state(true);
  let error = $state('');
  let loading = $state(false);
  let more = $state(true);
  let selected = $state<LogDetail | null>(null);
  let busy = $state(false);

  const PAGE = 100;

  function fullQuery(): string {
    return [applied.trim(), node ? `node:${node}` : ''].filter(Boolean).join(' ');
  }

  function params(extra: Record<string, string | number> = {}): string {
    const p = new URLSearchParams({ q: fullQuery(), filter: FILTERS[filter], limit: String(PAGE) });
    for (const [k, v] of Object.entries(extra)) p.set(k, String(v));
    return p.toString();
  }

  async function load() {
    loading = true;
    try {
      const r = await api.get<LogPage>(`/logs?${params()}`);
      entries = r.entries;
      sources = r.sources;
      geoip = r.geoip;
      store = r.store;
      more = r.entries.length === PAGE;
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  async function older() {
    const last = entries.at(-1);
    if (!last) return;
    const r = await api.get<LogPage>(`/logs?${params({ before_id: last.id })}`);
    entries = [...entries, ...r.entries];
    more = r.entries.length === PAGE;
  }

  async function poll() {
    if (!live || loading || error) return;
    const first = entries[0];
    try {
      const r = await api.get<LogPage>(`/logs?${params(first ? { after_id: first.id } : {})}`);
      sources = r.sources;
      if (r.entries.length) entries = [...r.entries, ...entries].slice(0, 1000);
    } catch {
      /* nächster Versuch */
    }
  }

  load();
  const timer = setInterval(poll, 3000);
  onDestroy(() => clearInterval(timer));

  function search(e: Event) {
    e.preventDefault();
    applied = query;
    load();
  }

  function showIp(ip: string) {
    query = applied = `ip:${ip}`;
    filter = 0;
    selected = null;
    load();
  }

  async function open(e: LogEntry) {
    if (selected?.id === e.id) {
      selected = null;
      return;
    }
    try {
      selected = await api.get<LogDetail>(`/logs/${e.id}`);
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err));
    }
  }

  async function ban(d: LogDetail) {
    busy = true;
    try {
      await api.post('/bans', { ip: d.ip, hours: 24, reason: `aus den Logs: ${d.method} ${d.host}${d.uri}`.slice(0, 250) });
      toasts.show('ok', `${d.ip} ist für 24 Stunden auf allen Nodes gesperrt.`);
      selected = await api.get<LogDetail>(`/logs/${d.id}`);
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err), 10000);
    } finally {
      busy = false;
    }
  }

  async function exclude(d: LogDetail) {
    busy = true;
    try {
      const r = await api.post<{ ok: boolean; added: number[]; host: string; error: string | null }>(`/logs/${d.id}/exclude`);
      if (!r.added.length) toasts.show('info', `Die Regeln sind für ${r.host} schon ausgenommen.`);
      else if (r.ok) toasts.show('ok', `Ausnahme ${r.added.join(', ')} für ${r.host} angelegt und übertragen.`);
      else toasts.show('warn', `Ausnahme gespeichert, aber nicht übertragen: ${r.error}`, 10000);
      selected = await api.get<LogDetail>(`/logs/${d.id}`);
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err), 10000);
    } finally {
      busy = false;
    }
  }

  const time = (iso: string) =>
    new Date(iso).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const day = (iso: string) => new Date(iso).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
  const today = new Date().toDateString();
  const short = (host: string) => host.split('.')[0];

  function statusTone(e: LogEntry): string {
    if (e.status === 0) return 'bad';
    if (e.status >= 400 || e.reason !== 'ok') return 'bad';
    if (e.status >= 300) return 'muted';
    return 'ok';
  }

  function reasonText(e: LogEntry): string {
    if (e.reason === 'waf') return `WAF ${e.waf_rules[0] ?? ''}`.trim();
    if (e.reason !== 'ok') return LOG_REASONS[e.reason].label;
    if (e.waf_rules.length) return `ok · WAF meldet ${e.waf_rules[0]}`;
    if (e.device) return 'ok · Gerät erkannt';
    return 'ok';
  }

  const delivering = $derived(sources.filter((s) => s.state !== 'offline' && s.state !== 'pending'));
  const offline = $derived(sources.filter((s) => s.state === 'offline'));
  const scoreRules = new Set([949110, 949111, 959100, 980130, 980140, 980170]);
</script>

<AppShell active="stats">
  <PageHeader
    title="Logs"
    subtitle={`${delivering.length} von ${sources.length} Node${sources.length === 1 ? '' : 's'} liefern${offline.length ? ` · ${offline.map((s) => s.node).join(', ')} puffert lokal und liefert nach` : ''}`}
  />
  <StatsTabs current="#/logs" />

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}
  {#if !loading && !error && entries.length === 0 && !applied && filter === 0}
    <Alert
      tone="info"
      title="Noch keine Einträge"
      text="Caddy schreibt das Zugriffs-Log, sobald TESSERACT_CADDY_ACCESS_LOG (Controller) bzw. TESSERACT_AGENT_ACCESS_LOG (Nodes) gesetzt ist – im Compose-Stack schon so. Neue Anfragen erscheinen hier nach wenigen Sekunden."
    />
  {/if}

  <form class="row toolbar" onsubmit={search}>
    <SegmentedControl
      groupLabel="Filter"
      options={['Alle', 'Abgelehnt', 'Ohne Zertifikat', 'WAF', 'IP-Filter']}
      bind:selected={filter}
      onChange={() => load()}
    />
    <label class="search">
      <Icon name="search" size={16} strokeWidth={2} />
      <span class="visually-hidden">Logs durchsuchen</span>
      <input type="search" placeholder="host:git status:403 ip:… rule:942100 oder Text" bind:value={query} />
    </label>
    <label class="node-select">
      <span>Node</span>
      <select class="input" bind:value={node} onchange={() => load()}>
        <option value="">Alle Nodes</option>
        {#each sources as s (s.node)}<option value={s.node}>{s.node}</option>{/each}
      </select>
    </label>
    <button type="button" class="live" aria-pressed={live} onclick={() => (live = !live)}>
      <span class="dot"></span>Live
    </button>
  </form>

  <div class="layout" class:with-detail={selected !== null}>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th scope="col">Zeit</th>
            <th scope="col">Host · Node</th>
            <th scope="col">Anfrage</th>
            <th scope="col">Status</th>
            <th scope="col">Wer</th>
            <th scope="col">Grund</th>
          </tr>
        </thead>
        <tbody>
          {#each entries as e (e.id)}
            <tr class:sel={selected?.id === e.id} onclick={() => open(e)}>
              <td class="mono small nowrap">
                {#if new Date(e.ts).toDateString() !== today}<span class="muted">{day(e.ts)} </span>{/if}{time(e.ts)}
              </td>
              <td class="nowrap"><span class="strong">{short(e.host)}</span> <span class="muted small">· {e.node}</span></td>
              <td class="mono small req">
                <button type="button" class="link" aria-expanded={selected?.id === e.id}>{e.method} {e.uri}</button>
              </td>
              <td class="mono small strong {statusTone(e)}">{e.status === 0 ? 'abgebrochen' : e.status}</td>
              <td class="small nowrap">
                {#if e.device}<span class="device">{e.device} · {e.person}</span>
                {:else}<span class="mono">{e.ip}</span>{#if e.country} <span class="muted">{e.country}</span>{/if}{/if}
              </td>
              <td class="small nowrap"><span class="key {LOG_REASONS[e.reason].tone}"></span>{reasonText(e)}</td>
            </tr>
          {:else}
            {#if !loading}<tr><td colspan="6" class="muted">Keine Treffer.</td></tr>{/if}
          {/each}
        </tbody>
      </table>
      {#if more && entries.length}
        <div class="more"><Button variant="ghost" size="sm" label="Ältere laden" onClick={older} /></div>
      {/if}
    </div>

    {#if selected}
      {@const d = selected}
      {@const rules = d.waf_rules.filter((r) => !scoreRules.has(r))}
      <aside class="card detail" aria-label="Details">
        <div class="row">
          <span class="muted small">{new Date(d.ts).toLocaleString('de-DE')} · {d.node}</span>
          <span class="spacer"></span>
          <Button variant="ghost" size="sm" icon="close" label="Schließen" onClick={() => (selected = null)} />
        </div>
        <h2>
          {#if d.reason === 'waf'}Von Coraza blockiert
          {:else if d.reason !== 'ok'}Abgelehnt: {LOG_REASONS[d.reason].label}
          {:else if d.status >= 500}Fehler beim Dienst
          {:else}Anfrage{/if}
        </h2>
        <p class="mono req-full">{d.method} {d.host}{d.uri}</p>
        <dl>
          {#if d.waf_rules.length}
            <dt>Regel</dt>
            <dd><span class="mono strong">{rules.join(', ') || d.waf_rules.join(', ')}</span>{#if d.waf_msg} · {d.waf_msg}{/if}</dd>
          {/if}
          {#if d.waf_score !== null}<dt>Anomalie-Score</dt><dd>{d.waf_score}</dd>{/if}
          <dt>Antwort</dt>
          <dd>
            {d.status === 0 ? 'Verbindung abgebrochen' : d.status}
            {#if d.reason !== 'ok'}, nie beim Dienst angekommen{:else} · {d.duration_ms.toLocaleString('de-DE')} ms · {formatBytes(d.size)}{/if}
          </dd>
          <dt>Client</dt>
          <dd><span class="mono">{d.ip}</span>{#if d.country} · {countryName(d.country)}{/if}</dd>
          {#if d.device}<dt>Gerät</dt><dd>{d.device} · {d.person}</dd>{/if}
          {#if d.user_agent}<dt>Browser</dt><dd class="small">{d.user_agent}</dd>{/if}
          <dt>Diese IP (24 h)</dt>
          <dd>{d.ip_requests} Anfragen, {d.ip_denied} abgelehnt{#if d.ip_banned} · <strong>gesperrt</strong>{/if}</dd>
        </dl>
        <div class="actions">
          {#if !d.ip_banned && !d.device}
            <Button variant="danger" size="sm" label="IP 24 h sperren" disabled={busy} onClick={() => ban(d)} />
          {/if}
          {#if rules.length && d.host_id}
            {#if rules.every((r) => d.waf_exclusions.includes(r))}
              <span class="muted small">Regel {rules.join(', ')} ist für diesen Host bereits ausgenommen.</span>
            {:else}
              <Button variant="secondary" size="sm" label={`Fehlalarm: Ausnahme für ${short(d.host)} anlegen`} disabled={busy} onClick={() => exclude(d)} />
            {/if}
          {/if}
          <Button variant="ghost" size="sm" label="Alle Einträge dieser IP" onClick={() => showIp(d.ip)} />
          {#if d.host_id}<Button variant="ghost" size="sm" label="Host-Sicherheit" href={`#/hosts/${d.host_id}/security`} />{/if}
        </div>
      </aside>
    {/if}
  </div>

  <p class="muted small">
    Suche: <span class="mono">host:git status:403 status:5xx ip:198.51.100.7 ip:198.51.100.0/24 reason:waf rule:942100 node:pi method:POST device:iphone country:DE</span>
    und freier Text (Teil der Adresse). {#if !geoip}Länder: GeoIP-Datenbank unter TESSERACT_GEOIP_DB hinterlegen.{/if}
    {#if store !== 'local'}Quelle: {store === 'loki' ? 'Loki' : 'VictoriaLogs'} (Einstellungen › Metriken).{/if}
    {#if sources.length}Letzter Eintrag: {sources.map((s) => `${s.node} ${formatAgo(s.last_entry_at)}`).join(' · ')}{/if}
  </p>
</AppShell>

<style>
  .toolbar {
    gap: 12px;
  }
  .search {
    flex: 1 1 260px;
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    padding: 0 12px;
    border-radius: var(--radius);
    background: var(--surface);
    border: 1px solid var(--border-input);
    color: var(--text-muted);
  }
  .search input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: transparent;
    color: var(--text);
    font: inherit;
  }
  .node-select {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-muted);
    font-size: 13px;
  }
  .live {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    padding: 0 14px;
    border-radius: var(--radius);
    border: 1px solid var(--border-input);
    background: transparent;
    color: var(--text-muted);
    font: inherit;
    font-weight: 500;
    cursor: pointer;
  }
  .live .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-faint);
  }
  .live[aria-pressed='true'] {
    color: var(--text);
  }
  .live[aria-pressed='true'] .dot {
    background: var(--ok);
    box-shadow: 0 0 0 3px rgba(76, 195, 138, 0.2);
  }
  .layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
    align-items: start;
  }
  .layout.with-detail {
    grid-template-columns: minmax(0, 1fr) minmax(300px, 380px);
  }
  @media (max-width: 1100px) {
    .layout.with-detail {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  tbody tr {
    cursor: pointer;
  }
  tbody tr:hover {
    background: var(--overlay);
  }
  tr.sel {
    background: rgba(139, 124, 246, 0.1);
    box-shadow: inset 3px 0 0 var(--accent);
  }
  .req {
    max-width: 420px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .link {
    padding: 0;
    border: none;
    background: none;
    color: inherit;
    font: inherit;
    cursor: pointer;
    text-align: left;
  }
  .nowrap {
    white-space: nowrap;
  }
  .small {
    font-size: 12px;
  }
  .strong {
    font-weight: 600;
  }
  .ok {
    color: var(--ok-text);
  }
  .bad {
    color: var(--bad-text);
  }
  .device {
    color: var(--accent-text);
  }
  .key {
    display: inline-block;
    width: 9px;
    height: 9px;
    border-radius: 3px;
    margin-right: 6px;
    background: var(--text-faint);
  }
  .key.waf {
    background: #14a399;
  }
  .key.mtls {
    background: #8b7cf6;
  }
  .key.ip {
    background: #cf7d45;
  }
  .key.bad {
    background: #f07167;
  }
  .more {
    display: flex;
    justify-content: center;
    padding: 8px;
    border-top: 1px solid var(--border);
  }
  .detail h2 {
    margin: 0;
    font-size: 17px;
  }
  .req-full {
    margin: 0;
    padding: 10px 12px;
    border-radius: var(--radius);
    background: var(--bg-sunken);
    font-size: 12px;
    overflow-wrap: anywhere;
  }
  dl {
    margin: 0;
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 8px 14px;
    font-size: 13px;
  }
  dt {
    color: var(--text-muted);
  }
  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
  .actions {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  p.small {
    margin: 0;
    line-height: 1.6;
  }
</style>

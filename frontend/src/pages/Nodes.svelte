<script lang="ts">
  import { onDestroy } from 'svelte';
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import Button from '../lib/components/Button.svelte';
  import TextField from '../lib/components/TextField.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import {
    api,
    formatAgo,
    formatDay,
    formatValue,
    MODULES,
    type JoinToken,
    type NodeDrift,
    type NodeInfo,
    type NodeState
  } from '../lib/api';
  import { applyNode } from '../lib/nodes';
  import { toasts } from '../lib/toast.svelte';

  let nodes = $state<NodeInfo[]>([]);
  let loaded = $state(false);
  let error = $state('');
  let busy = $state<string | null>(null);

  // Neuer Node
  let adding = $state(false);
  let newName = $state('');
  let newLocation = $state('');
  let formError = $state('');
  /** zuletzt erzeugtes Beitritts-Token (wird nur einmal angezeigt) */
  let join = $state<{ node: string; data: JoinToken } | null>(null);

  let configOpen = $state<number | null>(null);
  let configText = $state('');
  let drifts = $state<Record<number, NodeDrift>>({});
  let remove = $state<NodeInfo | null>(null);

  // Bearbeiten: Name (nur Agent-Nodes), Standort, öffentliche IPs
  let editing = $state<{ id: number; name: string; location: string; ips: string } | null>(null);

  function startEdit(n: NodeInfo) {
    editing = { id: n.id, name: n.name, location: n.location, ips: n.public_ips.join(', ') };
  }

  async function saveEdit(e: SubmitEvent) {
    e.preventDefault();
    const ed = editing;
    if (!ed) return;
    busy = `edit-${ed.id}`;
    try {
      await api.put(`/nodes/${ed.id}`, {
        name: ed.name,
        location: ed.location,
        public_ips: ed.ips.split(/[\s,;]+/).filter(Boolean)
      });
      editing = null;
      toasts.show('ok', 'Gespeichert.');
      await load();
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err), 10000);
    } finally {
      busy = null;
    }
  }

  async function load() {
    try {
      nodes = await api.get<NodeInfo[]>('/nodes');
      error = '';
      for (const n of nodes) {
        if (n.drift && !drifts[n.id]) drifts[n.id] = await api.get<NodeDrift>(`/nodes/${n.id}/drift`);
        if (!n.drift && drifts[n.id]) delete drifts[n.id];
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loaded = true;
    }
  }
  load();
  // Status der Agents regelmäßig nachladen
  const timer = setInterval(load, 10000);
  onDestroy(() => clearInterval(timer));

  async function run(key: string, fn: () => Promise<void>) {
    busy = key;
    try {
      await fn();
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      busy = null;
      await load();
    }
  }

  async function create() {
    formError = '';
    busy = 'create';
    try {
      const r = await api.post<{ node: NodeInfo; join: JoinToken }>('/nodes', {
        name: newName,
        location: newLocation
      });
      join = { node: r.node.name, data: r.join };
      adding = false;
      newName = newLocation = '';
      await load();
    } catch (e) {
      formError = e instanceof Error ? e.message : String(e);
    } finally {
      busy = null;
    }
  }

  const newToken = (n: NodeInfo) =>
    run(`token-${n.id}`, async () => {
      join = { node: n.name, data: await api.post<JoinToken>(`/nodes/${n.id}/token`) };
    });

  const approve = (n: NodeInfo) =>
    run(`approve-${n.id}`, async () => {
      await api.post(`/nodes/${n.id}/approve`);
      if (join?.node === n.name) join = null;
      toasts.show('ok', `${n.name} ist beigetreten. Der Agent holt jetzt seine Config ab.`);
    });

  const reject = (n: NodeInfo) =>
    run(`reject-${n.id}`, async () => {
      await api.post(`/nodes/${n.id}/reject`);
      toasts.show('info', `Beitritt von ${n.name} abgelehnt.`);
    });

  const apply = (n: NodeInfo) => run(`apply-${n.id}`, async () => void (await applyNode(n)));

  const overwrite = (n: NodeInfo) =>
    run(`overwrite-${n.id}`, async () => {
      const r = await api.post<{ ok: boolean; error: string | null }>(`/nodes/${n.id}/overwrite`);
      if (!r.ok) throw new Error(r.error ?? 'Überschreiben fehlgeschlagen');
      delete drifts[n.id];
      toasts.show('ok', `${n.name} bekommt wieder den Stand des Controllers.`);
    });

  const accept = (n: NodeInfo) =>
    run(`accept-${n.id}`, async () => {
      await api.post(`/nodes/${n.id}/accept`);
      delete drifts[n.id];
      toasts.show('info', `Lokale Änderung auf ${n.name} übernommen – bis zur nächsten Änderung im Controller.`);
    });

  async function doRemove() {
    const n = remove;
    remove = null;
    if (n) await run(`delete-${n.id}`, async () => void (await api.del(`/nodes/${n.id}`)));
  }

  async function toggleConfig(n: NodeInfo) {
    if (configOpen === n.id) {
      configOpen = null;
      return;
    }
    configOpen = n.id;
    configText = 'Lädt …';
    try {
      configText = JSON.stringify(await api.get(`/nodes/${n.id}/config`), null, 2);
    } catch (e) {
      configText = e instanceof Error ? e.message : String(e);
    }
  }

  function copy(text: string) {
    navigator.clipboard?.writeText(text).then(
      () => toasts.show('ok', 'Kopiert.'),
      () => toasts.show('warn', 'Kopieren nicht möglich – bitte markieren.')
    );
  }

  const fp = (hex: string | null) => (hex ? (hex.match(/.{2}/g) ?? []).join(':').toUpperCase() : '–');

  const STATE: Record<NodeState, { tone: 'ok' | 'warn' | 'bad' | 'neutral'; label: string }> = {
    online: { tone: 'ok', label: 'online' },
    drift: { tone: 'warn', label: 'lokal geändert' },
    offline: { tone: 'bad', label: 'offline' },
    error: { tone: 'bad', label: 'Fehler' },
    pending: { tone: 'neutral', label: 'wartet auf Beitritt' }
  };

  function syncLabel(n: NodeInfo): { text: string; tone: string } {
    if (n.state === 'pending') return { text: '–', tone: '' };
    if (n.last_apply_error) return { text: 'Fehler beim Laden', tone: 'bad' };
    if (n.drift) return { text: 'lokal geändert', tone: 'warn' };
    if (n.accepted) return { text: 'Abweichung übernommen', tone: 'warn' };
    if (!n.in_sync) return { text: n.kind === 'agent' ? 'wird abgeholt …' : 'nicht synchron', tone: 'warn' };
    return { text: 'synchron', tone: '' };
  }

  function modules(n: NodeInfo): string {
    if (n.modules === null) return 'noch nicht geprüft';
    return n.modules.map((m) => MODULES[m] ?? m).join(', ') || 'keine';
  }

  const missing = (n: NodeInfo) => (n.modules ? Object.keys(MODULES).filter((m) => !n.modules!.includes(m)) : []);

  const requests = $derived(nodes.filter((n) => n.join_state === 'pending'));
  const driftNodes = $derived(nodes.filter((n) => n.drift && drifts[n.id]));

  const compose = $derived(
    join
      ? `services:
  agent:
    image: tesseract-agent
    restart: unless-stopped
    environment:
      TESSERACT_AGENT_CONTROLLER: ${join.data.command.split('--controller ')[1]?.split(' ')[0] ?? ''}
      TESSERACT_AGENT_JOIN_TOKEN: ${join.data.token}
      TESSERACT_AGENT_CADDY_ADMIN_URL: http://caddy:2019
      TESSERACT_AGENT_WAF_LOG: /var/log/tesseract/waf.log
    volumes:
      - agent-data:/data
      - caddy-logs:/var/log/tesseract:ro`
      : ''
  );
</script>

<AppShell active="nodes">
  <PageHeader
    title="Nodes"
    subtitle="Jeder weitere Node meldet sich per Agent beim Controller – ausgehend per mTLS, kein offener Admin-Port, auch hinter NAT."
    primaryLabel="Node hinzufügen"
    onPrimary={() => ((adding = !adding), (formError = ''))}
  />

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if adding}
    <form class="card" onsubmit={(e) => (e.preventDefault(), create())}>
      <h2>Neuen Node anlegen</h2>
      <div class="form-grid">
        <TextField label="Name" bind:value={newName} placeholder="pi-eltern" hint="a–z, 0–9 und Bindestrich" error={formError} />
        <TextField label="Standort" bind:value={newLocation} placeholder="Elternhaus · hinter NAT" mono={false} />
      </div>
      <div class="row">
        <Button type="submit" label={busy === 'create' ? 'Legt an …' : 'Anlegen & Token erzeugen'} disabled={!newName.trim() || busy === 'create'} />
        <Button variant="ghost" label="Abbrechen" onClick={() => (adding = false)} />
      </div>
    </form>
  {/if}

  {#if join}
    <section class="card join" aria-labelledby="join-title">
      <div class="row">
        <h2 id="join-title">Beitritt für {join.node}</h2>
        <span class="spacer"></span>
        <StatusPill tone="neutral" label={`gültig bis ${new Date(join.data.expires_at).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}`} />
        <Button variant="ghost" size="sm" icon="close" label="Ausblenden" onClick={() => (join = null)} />
      </div>
      <ol>
        <li>Auf dem neuen Server (Linux mit Docker) diesen Befehl ausführen. Er richtet Caddy und Agent in <span class="mono">/opt/tesseract-node</span> ein und startet beide.</li>
        <li>Das Skript zeigt am Ende den Fingerabdruck des Agent-Schlüssels.</li>
        <li>Hier die Anfrage bestätigen, wenn der Fingerabdruck übereinstimmt. Danach holt der Agent die Config ab.</li>
      </ol>
      <div class="code-head"><span class="eyebrow">Installieren</span><Button variant="ghost" size="sm" icon="clipboard" label="Kopieren" onClick={() => copy(join!.data.install_command)} /></div>
      <pre class="code">{join.data.install_command}</pre>
      <p class="muted small">
        Ohne Docker auf dem Server: <span class="mono">--install-docker</span> anhängen. Sind die Images nicht öffentlich:
        <span class="mono">--registry-token &lt;Token mit read:packages&gt;</span>. Skript vorher ansehen:
        <a href={join.data.install_command.match(/https?:\/\/\S+\/install\/node\.sh/)?.[0] ?? '#'} target="_blank" rel="noopener">node.sh</a>
        · Prüfsumme <span class="mono sha">{join.data.install_sha256}</span>
      </p>
      <details>
        <summary class="small">Andere Wege: Docker Compose von Hand oder nur der Agent</summary>
        <div class="code-head"><span class="eyebrow">Docker Compose (neben Caddy)</span><Button variant="ghost" size="sm" icon="clipboard" label="Kopieren" onClick={() => copy(compose)} /></div>
        <pre class="code">{compose}</pre>
        <div class="code-head"><span class="eyebrow">Agent per Kommandozeile</span><Button variant="ghost" size="sm" icon="clipboard" label="Kopieren" onClick={() => copy(join!.data.command)} /></div>
        <pre class="code">{join.data.command}</pre>
      </details>
      <p class="muted small">Das Token ist 30 Minuten gültig und nur einmal verwendbar. Es wird nicht wieder angezeigt.</p>
    </section>
  {/if}

  {#each requests as n (n.id)}
    <section class="card request" aria-label={`Beitrittsanfrage ${n.name}`}>
      <div class="row">
        <h2>Agent möchte als <span class="mono">{n.name}</span> beitreten</h2>
        <span class="spacer"></span>
        <Button variant="secondary" label="Ablehnen" disabled={busy !== null} onClick={() => reject(n)} />
        <Button label={busy === `approve-${n.id}` ? 'Bestätigt …' : 'Bestätigen'} icon="check" disabled={busy !== null} onClick={() => approve(n)} />
      </div>
      <dl class="facts">
        <dt>Rechner</dt><dd class="mono">{n.join_hostname ?? '–'}</dd>
        <dt>Angefragt</dt><dd>{formatAgo(n.join_requested_at)}</dd>
        <dt>Schlüssel</dt><dd class="mono fp">{fp(n.join_key_fingerprint)}</dd>
      </dl>
      <p class="muted small">Nur bestätigen, wenn der Agent beim Start denselben Fingerabdruck angezeigt hat.</p>
    </section>
  {/each}

  {#each driftNodes as n (n.id)}
    {@const d = drifts[n.id]}
    <section class="card drift" aria-labelledby={`drift-${n.id}`}>
      <div class="row">
        <div class="titles">
          <h2 id={`drift-${n.id}`}>Abweichung auf {n.name}</h2>
          <span class="muted small">Die laufende Config unterscheidet sich vom Stand des Controllers (seit {formatAgo(d.since)}).</span>
        </div>
        <span class="spacer"></span>
        <Button variant="secondary" label="Änderung übernehmen" disabled={busy !== null} onClick={() => accept(n)} />
        <Button label="Mit Controller überschreiben" disabled={busy !== null} onClick={() => overwrite(n)} />
      </div>
      <div class="diff mono">
        {#each d.changes as c (c.path)}
          <div class="diff-path">{#if c.host}<span class="diff-host">{c.host}</span> · {/if}{c.path}</div>
          {#if c.kind !== 'added'}<div class="minus">- {formatValue(c.before)}</div>{/if}
          {#if c.kind !== 'removed'}<div class="plus">+ {formatValue(c.after)}</div>{/if}
        {:else}
          <div class="muted">Keine Einzelheiten verfügbar.</div>
        {/each}
      </div>
      <p class="muted small">
        „Übernehmen“ lässt die lokale Änderung laufen, bis der Controller die nächste Änderung an diesen Node überträgt.
        Dauerhafte Änderungen gehören in den Controller.
      </p>
    </section>
  {/each}

  <section aria-label="Alle Nodes" class="grid">
    {#each nodes as n (n.id)}
      {@const st = STATE[n.state]}
      {@const sync = syncLabel(n)}
      <article class="card node {n.state}">
        <div class="node-head">
          <div class="titles">
            <h2 class="mono">{n.name}</h2>
            <span class="muted small">{n.location || '–'} · {n.kind === 'local' ? 'lokal (direkt)' : 'Agent'}</span>
            {#if n.public_ips.length}<span class="muted small mono">{n.public_ips.join(', ')}</span>{/if}
          </div>
          <StatusPill tone={st.tone} label={st.label} />
        </div>
        {#if n.state === 'pending'}
          <p class="muted small">
            {#if n.join_state === 'rejected'}Beitritt abgelehnt – für einen neuen Versuch ein neues Token erzeugen.
            {:else if n.join_state === 'pending'}Anfrage liegt vor – oben bestätigen.
            {:else if n.join_open}Token erzeugt, gültig bis {new Date(n.join_expires_at!).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}. Agent noch nicht gemeldet.
            {:else}Token abgelaufen – neues erzeugen.{/if}
          </p>
        {:else}
          <dl class="stats">
            <div><dt>Caddy</dt><dd>{n.caddy_version ?? '–'}</dd></div>
            <div><dt>Hosts</dt><dd>{n.hosts}</dd></div>
            <div><dt>Letzter Kontakt</dt><dd class:bad={n.state === 'offline'}>{formatAgo(n.last_seen_at)}</dd></div>
            <div><dt>Konfiguration</dt><dd class={sync.tone}>{sync.text}</dd></div>
            <div class="wide"><dt>Module</dt><dd>{modules(n)}</dd></div>
            {#if n.kind === 'agent'}
              <div><dt>Agent</dt><dd>{n.agent_version ?? '–'}</dd></div>
              <div><dt>Zertifikat bis</dt><dd>{formatDay(n.cert_not_after)}</dd></div>
            {/if}
          </dl>
          {#if missing(n).length}
            <p class="warn small">Fehlt: {missing(n).map((m) => MODULES[m]).join(', ')} – Hosts mit WAF bzw. DNS-01 lassen sich auf diesem Node nicht laden.</p>
          {/if}
          {#if n.last_apply_error}<p class="bad small">{n.last_apply_error}</p>{/if}
        {/if}
        {#if editing?.id === n.id}
          <form class="edit" onsubmit={saveEdit}>
            {#if n.kind === 'agent'}
              <label class="field">Name<input class="input mono" bind:value={editing.name} maxlength="64" required /></label>
            {/if}
            <label class="field">Standort<input class="input" bind:value={editing.location} maxlength="128" /></label>
            <label class="field">
              Öffentliche IP(s)
              <input class="input mono" placeholder="203.0.113.7, 2001:db8::7" bind:value={editing.ips} />
              <span class="muted small">
                Damit prüft „Host anlegen“, ob der DNS-Eintrag auf diesen Node zeigt. Bei wechselnder IP (DDNS) oder hinter dem
                Cloudflare-Proxy leer lassen.
              </span>
            </label>
            <div class="row">
              <Button type="submit" size="sm" label={busy === `edit-${n.id}` ? 'Speichert …' : 'Speichern'} disabled={busy !== null} />
              <Button variant="ghost" size="sm" label="Abbrechen" onClick={() => (editing = null)} />
            </div>
          </form>
        {/if}
        <div class="row actions">
          <Button variant="ghost" size="sm" label="Bearbeiten" disabled={busy !== null || editing?.id === n.id} onClick={() => startEdit(n)} />
          {#if n.state !== 'pending'}
            <Button variant="secondary" size="sm" label={configOpen === n.id ? 'Config schließen' : 'Config ansehen'} onClick={() => toggleConfig(n)} />
            <Button variant="secondary" size="sm" icon="refresh" label={busy === `apply-${n.id}` ? 'Überträgt …' : 'Neu übertragen'} disabled={busy !== null} onClick={() => apply(n)} />
          {/if}
          {#if n.kind === 'agent'}
            <Button variant="ghost" size="sm" label="Neues Token" disabled={busy !== null} onClick={() => newToken(n)} />
            <Button variant="ghost" size="sm" icon="trash" label="Löschen" disabled={busy !== null || n.hosts > 0} onClick={() => (remove = n)} />
          {/if}
        </div>
        {#if configOpen === n.id}<pre class="code config">{configText}</pre>{/if}
      </article>
    {/each}
  </section>

  {#if loaded && nodes.length === 1}
    <p class="muted small">
      Bisher läuft nur der lokale Caddy. Weitere Server – z. B. ein Raspberry Pi im Elternhaus – kommen über „Node hinzufügen“ dazu.
    </p>
  {/if}

  {#if remove}
    <ConfirmDialog
      title={`Node „${remove.name}“ löschen?`}
      text="Das Node-Zertifikat verliert sofort seine Gültigkeit beim Controller. Caddy auf dem Server läuft mit dem letzten Stand weiter, bis er gestoppt wird."
      word="löschen"
      confirmLabel="Node löschen"
      onConfirm={doRemove}
      onCancel={() => (remove = null)}
    />
  {/if}
</AppShell>

<style>
  .sha {
    font-size: 11px;
    overflow-wrap: anywhere;
  }
  details summary {
    cursor: pointer;
    color: var(--text-muted);
  }
  details[open] {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 14px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 14px;
  }
  h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
  }
  .node.drift,
  .card.drift,
  .card.request {
    border-color: rgba(229, 164, 67, 0.45);
  }
  .node.offline,
  .node.error {
    border-color: rgba(240, 113, 103, 0.45);
  }
  .node-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }
  .titles {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }
  .stats {
    margin: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px 16px;
  }
  .stats div {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .stats .wide {
    grid-column: 1 / -1;
  }
  .stats dt {
    font-size: 12px;
    color: var(--text-muted);
  }
  .stats dd {
    margin: 0;
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
  }
  .facts {
    margin: 0;
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 6px 16px;
    font-size: 13px;
  }
  .facts dt {
    color: var(--text-muted);
  }
  .facts dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
  .fp {
    font-size: 12px;
  }
  .edit {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-top: 4px;
    border-top: 1px solid var(--border);
  }
  .actions {
    margin-top: auto;
    gap: 8px;
  }
  .small {
    font-size: 13px;
    margin: 0;
    line-height: 1.5;
  }
  .warn {
    color: var(--warn-text);
  }
  .bad {
    color: var(--bad-text);
  }
  ol {
    margin: 0;
    padding-left: 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    line-height: 1.5;
  }
  .code-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  pre.code {
    overflow-x: auto;
    white-space: pre;
    font-size: 12px;
  }
  pre.config {
    max-height: 420px;
  }
  .diff {
    overflow-x: auto;
    padding: 10px 0;
    border-radius: var(--radius);
    background: var(--bg-sunken);
    border: 1px solid var(--border);
    font-size: 12px;
    line-height: 1.7;
  }
  .diff > div {
    padding: 0 14px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .diff-path {
    color: var(--text-muted);
    margin-top: 6px;
  }
  .diff-host {
    color: var(--text);
  }
  .minus {
    color: #f59a90;
    background: rgba(240, 113, 103, 0.1);
  }
  .plus {
    color: #7fd9ac;
    background: rgba(76, 195, 138, 0.1);
  }
</style>

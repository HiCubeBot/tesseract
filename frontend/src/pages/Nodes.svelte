<script lang="ts">
  import { locale, t } from '../lib/i18n';
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
  /** offenes „…“-Menü und aufgeklappte Details je Node */
  let menu = $state<number | null>(null);
  let details = $state<Record<number, boolean>>({});

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
      toasts.show('ok', t('Gespeichert.'));
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
      toasts.show('ok', t('{0} ist beigetreten. Der Agent holt jetzt seine Config ab.', n.name));
    });

  const reject = (n: NodeInfo) =>
    run(`reject-${n.id}`, async () => {
      await api.post(`/nodes/${n.id}/reject`);
      toasts.show('info', t('Beitritt von {0} abgelehnt.', n.name));
    });

  const apply = (n: NodeInfo) => run(`apply-${n.id}`, async () => void (await applyNode(n)));

  const overwrite = (n: NodeInfo) =>
    run(`overwrite-${n.id}`, async () => {
      const r = await api.post<{ ok: boolean; error: string | null }>(`/nodes/${n.id}/overwrite`);
      if (!r.ok) throw new Error(r.error ?? t('Überschreiben fehlgeschlagen'));
      delete drifts[n.id];
      toasts.show('ok', t('{0} bekommt wieder den Stand des Controllers.', n.name));
    });

  const accept = (n: NodeInfo) =>
    run(`accept-${n.id}`, async () => {
      await api.post(`/nodes/${n.id}/accept`);
      delete drifts[n.id];
      toasts.show('info', t('Lokale Änderung auf {0} übernommen – bis zur nächsten Änderung im Controller.', n.name));
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
    configText = t('Lädt …');
    try {
      configText = JSON.stringify(await api.get(`/nodes/${n.id}/config`), null, 2);
    } catch (e) {
      configText = e instanceof Error ? e.message : String(e);
    }
  }

  function copy(text: string) {
    navigator.clipboard?.writeText(text).then(
      () => toasts.show('ok', t('Kopiert.')),
      () => toasts.show('warn', t('Kopieren nicht möglich – bitte markieren.'))
    );
  }

  const fp = (hex: string | null) => (hex ? (hex.match(/.{2}/g) ?? []).join(':').toUpperCase() : '–');

  const STATE: Record<NodeState, { tone: 'ok' | 'warn' | 'bad' | 'neutral'; label: string }> = {
    online: { tone: 'ok', label: t('online') },
    drift: { tone: 'warn', label: t('lokal geändert') },
    offline: { tone: 'bad', label: t('offline') },
    error: { tone: 'bad', label: t('Fehler') },
    pending: { tone: 'neutral', label: t('wartet auf Beitritt') }
  };

  function syncLabel(n: NodeInfo): { text: string; tone: string } {
    if (n.state === 'pending') return { text: '–', tone: '' };
    if (n.last_apply_error) return { text: t('Fehler beim Laden'), tone: 'bad' };
    if (n.drift) return { text: t('lokal geändert'), tone: 'warn' };
    if (n.accepted) return { text: t('Abweichung übernommen'), tone: 'warn' };
    if (!n.in_sync) return { text: n.kind === 'agent' ? t('wird abgeholt …') : t('nicht synchron'), tone: 'warn' };
    return { text: t('synchron'), tone: '' };
  }

  function modules(n: NodeInfo): string {
    if (n.modules === null) return t('noch nicht geprüft');
    return n.modules.map((m) => MODULES[m] ?? m).join(', ') || 'keine';
  }

  function hostsLabel(n: NodeInfo): string {
    if (n.hosts === 0) return '0';
    if (n.hosts_public === n.hosts) return t('{0} (alle öffentlich)', n.hosts);
    if (n.hosts_public === 0) return t('{0} (keiner öffentlich)', n.hosts);
    return t('{0} ({1} öffentlich)', n.hosts, n.hosts_public);
  }

  /** https://tesseract.example.org:8443/ → tesseract.example.org:8443 */
  const shortUrl = (u: string) => u.replace(/^https?:\/\//, '').replace(/\/$/, '');

  const NETWORK: Record<string, { label: string; title: string }> = {
    intern: { label: t('intern'), title: t('Verbindung aus einem der internen Netze') },
    privat: { label: t('privat'), title: t('Verbindung aus einem privaten Adressbereich (LAN, VPN, CGNAT)') },
    internet: { label: t('Internet'), title: t('Verbindung über das Internet') }
  };

  // Beispielbefehl: Adresse, die schon ein Agent nutzt, sonst die der Oberfläche
  const controllerHint = $derived(
    nodes.find((x) => x.controller_url)?.controller_url ?? location.origin
  );

  function startAdd() {
    adding = true;
    formError = '';
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function menuAction(fn: () => void) {
    menu = null;
    fn();
  }

  const missing = (n: NodeInfo) => (n.modules ? Object.keys(MODULES).filter((m) => !n.modules!.includes(m)) : []);

  const requests = $derived(nodes.filter((n) => n.join_state === 'pending'));
  const driftNodes = $derived(nodes.filter((n) => n.drift && drifts[n.id]));

  const compose = $derived(
    join
      ? t('services:\n  agent:\n    image: tesseract-agent\n    restart: unless-stopped\n    environment:\n      TESSERACT_AGENT_CONTROLLER: {0}\n      TESSERACT_AGENT_JOIN_TOKEN: {1}\n      TESSERACT_AGENT_CADDY_ADMIN_URL: http://caddy:2019\n      TESSERACT_AGENT_WAF_LOG: /var/log/tesseract/waf.log\n    volumes:\n      - agent-data:/data\n      - caddy-logs:/var/log/tesseract:ro', join.data.command.split('--controller ')[1]?.split(' ')[0] ?? '', join.data.token)
      : ''
  );
</script>

<svelte:window onclick={() => (menu = null)} />

<AppShell active="nodes">
  <PageHeader
    title={t('Nodes')}
    subtitle={t('Jeder weitere Node meldet sich per Agent beim Controller – ausgehend per mTLS, kein offener Admin-Port, auch hinter NAT.')}
    primaryLabel={t('Node hinzufügen')}
    onPrimary={() => ((adding = !adding), (formError = ''))}
  />

  {#if error}<Alert tone="bad" title={t('Fehler')} text={error} />{/if}

  {#if adding}
    <form class="card" onsubmit={(e) => (e.preventDefault(), create())}>
      <h2>{t('Neuen Node anlegen')}</h2>
      <div class="form-grid">
        <TextField label={t('Name')} bind:value={newName} placeholder={t('pi-eltern')} hint={t('a–z, 0–9 und Bindestrich')} error={formError} />
        <TextField label={t('Standort')} bind:value={newLocation} placeholder={t('Elternhaus · hinter NAT')} mono={false} />
      </div>
      <div class="row">
        <Button type="submit" label={busy === 'create' ? t('Legt an …') : t('Anlegen & Token erzeugen')} disabled={!newName.trim() || busy === 'create'} />
        <Button variant="ghost" label={t('Abbrechen')} onClick={() => (adding = false)} />
      </div>
    </form>
  {/if}

  {#if join}
    <section class="card join" aria-labelledby="join-title">
      <div class="row">
        <h2 id="join-title">{t('Beitritt für {0}', join.node)}</h2>
        <span class="spacer"></span>
        <StatusPill tone="neutral" label={t('gültig bis {0}', new Date(join.data.expires_at).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' }))} />
        <Button variant="ghost" size="sm" icon="close" label={t('Ausblenden')} onClick={() => (join = null)} />
      </div>
      <ol>
        <li>{t('Auf dem neuen Server (Linux mit Docker) diesen Befehl ausführen. Er richtet Caddy und Agent in')} <span class="mono">/opt/tesseract-node</span> {t('ein und startet beide.')}</li>
        <li>{t('Das Skript zeigt am Ende den Fingerabdruck des Agent-Schlüssels.')}</li>
        <li>{t('Hier die Anfrage bestätigen, wenn der Fingerabdruck übereinstimmt. Danach holt der Agent die Config ab.')}</li>
      </ol>
      <div class="code-head"><span class="eyebrow">{t('Installieren')}</span><Button variant="ghost" size="sm" icon="clipboard" label={t('Kopieren')} onClick={() => copy(join!.data.install_command)} /></div>
      <pre class="code">{join.data.install_command}</pre>
      <p class="muted small">
        {t('Ohne Docker auf dem Server:')} <span class="mono">--install-docker</span> {t('anhängen. Sind die Images nicht öffentlich:')}
        <span class="mono">{t('--registry-token <Token mit read:packages>')}</span>{t('. Skript vorher ansehen:')}
        <a href={join.data.install_command.match(/https?:\/\/\S+\/install\/node\.sh/)?.[0] ?? '#'} target="_blank" rel="noopener">node.sh</a>
        {t('· Prüfsumme')} <span class="mono sha">{join.data.install_sha256}</span>
      </p>
      <details>
        <summary class="small">{t('Andere Wege: Docker Compose von Hand oder nur der Agent')}</summary>
        <div class="code-head"><span class="eyebrow">{t('Docker Compose (neben Caddy)')}</span><Button variant="ghost" size="sm" icon="clipboard" label={t('Kopieren')} onClick={() => copy(compose)} /></div>
        <pre class="code">{compose}</pre>
        <div class="code-head"><span class="eyebrow">{t('Agent per Kommandozeile')}</span><Button variant="ghost" size="sm" icon="clipboard" label={t('Kopieren')} onClick={() => copy(join!.data.command)} /></div>
        <pre class="code">{join.data.command}</pre>
      </details>
      <p class="muted small">{t('Das Token ist 30 Minuten gültig und nur einmal verwendbar. Es wird nicht wieder angezeigt.')}</p>
    </section>
  {/if}

  {#each requests as n (n.id)}
    <section class="card request" aria-label={t('Beitrittsanfrage {0}', n.name)}>
      <div class="row">
        <h2>{t('Agent möchte als')} <span class="mono">{n.name}</span> {t('beitreten')}</h2>
        <span class="spacer"></span>
        <Button variant="secondary" label={t('Ablehnen')} disabled={busy !== null} onClick={() => reject(n)} />
        <Button label={busy === `approve-${n.id}` ? t('Bestätigt …') : t('Bestätigen')} icon="check" disabled={busy !== null} onClick={() => approve(n)} />
      </div>
      <dl class="facts">
        <dt>{t('Rechner')}</dt><dd class="mono">{n.join_hostname ?? '–'}</dd>
        <dt>{t('Angefragt')}</dt><dd>{formatAgo(n.join_requested_at)}</dd>
        <dt>{t('Schlüssel')}</dt><dd class="mono fp">{fp(n.join_key_fingerprint)}</dd>
      </dl>
      <p class="muted small">{t('Nur bestätigen, wenn der Agent beim Start denselben Fingerabdruck angezeigt hat.')}</p>
    </section>
  {/each}

  {#each driftNodes as n (n.id)}
    {@const d = drifts[n.id]}
    <section class="card drift" aria-labelledby={`drift-${n.id}`}>
      <div class="row">
        <div class="titles">
          <h2 id={`drift-${n.id}`}>{t('Abweichung auf {0}', n.name)}</h2>
          <span class="muted small">{t('Die laufende Config unterscheidet sich vom Stand des Controllers (seit {0}).', formatAgo(d.since))}</span>
        </div>
        <span class="spacer"></span>
        <Button variant="secondary" label={t('Änderung übernehmen')} disabled={busy !== null} onClick={() => accept(n)} />
        <Button label={t('Mit Controller überschreiben')} disabled={busy !== null} onClick={() => overwrite(n)} />
      </div>
      <div class="diff mono">
        {#each d.changes as c (c.path)}
          <div class="diff-path">{#if c.host}<span class="diff-host">{c.host}</span> · {/if}{c.path}</div>
          {#if c.kind !== 'added'}<div class="minus">- {formatValue(c.before)}</div>{/if}
          {#if c.kind !== 'removed'}<div class="plus">+ {formatValue(c.after)}</div>{/if}
        {:else}
          <div class="muted">{t('Keine Einzelheiten verfügbar.')}</div>
        {/each}
      </div>
      <p class="muted small">
        {t('„Übernehmen“ lässt die lokale Änderung laufen, bis der Controller die nächste Änderung an diesen Node überträgt. Dauerhafte Änderungen gehören in den Controller.')}
      </p>
    </section>
  {/each}

  <section aria-label={t('Alle Nodes')} class="grid">
    {#each nodes as n (n.id)}
      {@const st = STATE[n.state]}
      {@const sync = syncLabel(n)}
      {@const net = n.network ? NETWORK[n.network] : null}
      <article class="card node {n.state}">
        <div class="node-head">
          <div class="titles">
            <h2 class="mono">{n.name}</h2>
            <span class="muted small">{n.location || (n.kind === 'local' ? 'lokal' : '–')}</span>
          </div>
          <StatusPill tone={st.tone} label={st.label} />
        </div>
        {#if n.state === 'pending'}
          <p class="muted small">
            {#if n.join_state === 'rejected'}{t('Beitritt abgelehnt – für einen neuen Versuch ein neues Token erzeugen.')}
            {:else if n.join_state === 'pending'}{t('Anfrage liegt vor – oben bestätigen.')}
            {:else if n.join_open}{t('Token erzeugt, gültig bis {0}. Agent noch nicht gemeldet.', new Date(n.join_expires_at!).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' }))}
            {:else}{t('Token abgelaufen – neues erzeugen.')}{/if}
          </p>
        {:else}
          <dl class="stats">
            <div><dt>{t('Caddy')}</dt><dd>{n.caddy_version?.split(' ')[0] ?? '–'}</dd></div>
            <div><dt>{t('Hosts')}</dt><dd>{hostsLabel(n)}</dd></div>
            <div><dt>{t('Letzter Kontakt')}</dt><dd class:bad={n.state === 'offline'}>{formatAgo(n.last_seen_at)}</dd></div>
            <div><dt>{t('Konfiguration')}</dt><dd class={sync.tone}>{sync.text}</dd></div>
            <div class="wide">
              <dt>{t('Verbindung zum Controller')}</dt>
              {#if n.kind === 'local'}
                <dd>{t('lokal (direkt)')}</dd>
              {:else}
                <dd class="mono conn">{n.controller_url ? shortUrl(n.controller_url) : '–'}</dd>
                {#if net}
                  <dd><span class="chip {n.network}" title={`${net.title}${n.agent_ip ? ` · ${n.agent_ip}` : ''}`}>{net.label}</span></dd>
                {/if}
              {/if}
            </div>
            {#if details[n.id]}
              <div class="wide"><dt>{t('Module')}</dt><dd>{modules(n)}</dd></div>
              {#if n.kind === 'agent'}
                <div><dt>{t('Agent')}</dt><dd>{n.agent_version ?? '–'}</dd></div>
                <div><dt>{t('Zertifikat bis')}</dt><dd>{formatDay(n.cert_not_after)}</dd></div>
                <div class="wide"><dt>{t('IP der Verbindung')}</dt><dd class="mono">{n.agent_ip ?? '–'}</dd></div>
              {/if}
              <div class="wide"><dt>{t('Öffentliche IPs')}</dt><dd class="mono">{n.public_ips.join(', ') || '–'}</dd></div>
            {/if}
          </dl>
          {#if missing(n).length}
            <p class="warn small">{t('Fehlt: {0} – Hosts mit WAF bzw. DNS-01 lassen sich auf diesem Node nicht laden.', missing(n).map((m) => MODULES[m]).join(', '))}</p>
          {/if}
          {#if n.last_apply_error}<p class="bad small">{n.last_apply_error}</p>{/if}
        {/if}
        {#if editing?.id === n.id}
          <form class="edit" onsubmit={saveEdit}>
            {#if n.kind === 'agent'}
              <label class="field">{t('Name')}<input class="input mono" bind:value={editing.name} maxlength="64" required /></label>
            {/if}
            <label class="field">{t('Standort')}<input class="input" bind:value={editing.location} maxlength="128" /></label>
            <label class="field">
              {t('Öffentliche IP(s)')}
              <input class="input mono" placeholder={t('203.0.113.7, 2001:db8::7')} bind:value={editing.ips} />
              <span class="muted small">
                {t('Damit prüft „Host anlegen“, ob der DNS-Eintrag auf diesen Node zeigt. Bei wechselnder IP (DDNS) oder hinter dem Cloudflare-Proxy leer lassen.')}
              </span>
            </label>
            <div class="row">
              <Button type="submit" size="sm" label={busy === `edit-${n.id}` ? t('Speichert …') : t('Speichern')} disabled={busy !== null} />
              <Button variant="ghost" size="sm" label={t('Abbrechen')} onClick={() => (editing = null)} />
            </div>
          </form>
        {/if}
        <div class="actions">
          {#if n.state !== 'pending'}
            <div class="full">
              <Button variant="secondary" size="sm" label={configOpen === n.id ? t('Config schließen') : t('Config ansehen')} onClick={() => toggleConfig(n)} />
            </div>
          {/if}
          <div class="row-actions">
            <div class="full">
              {#if n.state !== 'pending'}
                <Button variant="secondary" size="sm" label={busy === `apply-${n.id}` ? t('Überträgt …') : t('Neu synchronisieren')} disabled={busy !== null} onClick={() => apply(n)} />
              {:else}
                <Button variant="secondary" size="sm" label={t('Neues Token')} disabled={busy !== null} onClick={() => newToken(n)} />
              {/if}
            </div>
            <div class="menu-wrap">
              <button
                type="button"
                class="more"
                aria-label={t('Weitere Aktionen für {0}', n.name)}
                aria-haspopup="menu"
                aria-expanded={menu === n.id}
                onclick={(e) => {
                  e.stopPropagation();
                  menu = menu === n.id ? null : n.id;
                }}>···</button
              >
              {#if menu === n.id}
                <div class="menu" role="menu">
                  <button type="button" role="menuitem" onclick={() => menuAction(() => startEdit(n))}>{t('Bearbeiten')}</button>
                  {#if n.state !== 'pending'}
                    <button type="button" role="menuitem" onclick={() => menuAction(() => (details[n.id] = !details[n.id]))}>
                      {details[n.id] ? t('Details ausblenden') : t('Details anzeigen')}
                    </button>
                    {#if n.kind === 'agent'}
                      <button type="button" role="menuitem" disabled={busy !== null} onclick={() => menuAction(() => newToken(n))}>{t('Neues Token')}</button>
                    {/if}
                  {/if}
                  {#if n.kind === 'agent'}
                    <button
                      type="button"
                      role="menuitem"
                      class="danger"
                      disabled={busy !== null || n.hosts > 0}
                      title={n.hosts > 0 ? t('Erst die Hosts auf andere Nodes verschieben') : undefined}
                      onclick={() => menuAction(() => (remove = n))}>{t('Löschen')}</button
                    >
                  {/if}
                </div>
              {/if}
            </div>
          </div>
        </div>
      </article>
    {/each}
  </section>

  {#if configOpen !== null}
    <section class="card" aria-labelledby="config-title">
      <div class="row">
        <h2 id="config-title">{t('Config von')} <span class="mono">{nodes.find((x) => x.id === configOpen)?.name ?? ''}</span></h2>
        <span class="spacer"></span>
        <Button variant="ghost" size="sm" icon="close" label={t('Schließen')} onClick={() => (configOpen = null)} />
      </div>
      <pre class="code config">{configText}</pre>
    </section>
  {/if}

  <section class="card connect" aria-labelledby="connect-title">
    <h2 id="connect-title">{t('Neuen Node verbinden')}</h2>
    <ol>
      <li>{t('Node anlegen – dabei entsteht ein Beitritts-Token.')}</li>
      <li>
        {t('Auf dem Server den Installationsbefehl ausführen. Er richtet Caddy mit den nötigen Modulen und den Agent ein – der Agent erzeugt eigene Schlüssel und baut eine mTLS-Verbindung zum Controller auf.')}
      </li>
      <li>{t('Node hier bestätigen. Danach überträgt der Controller die Config.')}</li>
    </ol>
    <pre class="code">{`tesseract-agent join \\\n  --controller ${controllerHint} \\\n  --token [BEITRITTS-TOKEN]`}</pre>
    <p class="muted small">{t('Token ist 30 Minuten gültig und nur einmal verwendbar.')}</p>
  </section>

  {#if loaded && nodes.length === 1}
    <p class="muted small">
      {t('Bisher läuft nur der lokale Caddy. Weitere Server – z. B. ein Raspberry Pi im Elternhaus – kommen über „Node hinzufügen“ dazu.')}
    </p>
  {/if}

  {#if remove}
    <ConfirmDialog
      title={t('Node „{0}“ löschen?', remove.name)}
      text={t('Das Node-Zertifikat verliert sofort seine Gültigkeit beim Controller. Caddy auf dem Server läuft mit dem letzten Stand weiter, bis er gestoppt wird.')}
      word="löschen"
      confirmLabel={t('Node löschen')}
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
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 14px;
  }
  .conn {
    font-size: 13px;
    overflow-wrap: anywhere;
  }
  .chip {
    display: inline-block;
    margin-top: 4px;
    padding: 0 8px;
    border-radius: 999px;
    font-size: 11px;
    line-height: 20px;
    font-weight: 500;
    background: var(--surface-raised);
    color: var(--text-muted);
  }
  .chip.intern,
  .chip.privat {
    background: rgba(76, 195, 138, 0.14);
    color: var(--ok-text);
  }
  .chip.internet {
    background: rgba(229, 164, 67, 0.14);
    color: var(--warn-text);
  }
  .actions {
    margin-top: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .row-actions {
    display: flex;
    gap: 8px;
  }
  .full {
    flex: 1;
    display: flex;
    min-width: 0;
  }
  .full :global(.btn) {
    flex: 1;
    justify-content: center;
  }
  .menu-wrap {
    position: relative;
    display: flex;
  }
  .more {
    min-height: 32px;
    padding: 0 12px;
    border-radius: var(--radius);
    border: 1px solid var(--border-input);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    letter-spacing: 1px;
  }
  .more:hover {
    color: var(--text);
  }
  .menu {
    position: absolute;
    right: 0;
    bottom: calc(100% + 6px);
    z-index: 5;
    min-width: 170px;
    padding: 4px;
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  }
  .menu button {
    text-align: left;
    padding: 8px 10px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: var(--text);
    font: inherit;
    font-size: 13px;
    cursor: pointer;
  }
  .menu button:hover:not(:disabled) {
    background: var(--surface-hover);
  }
  .menu button:disabled {
    color: var(--text-muted);
    cursor: not-allowed;
  }
  .menu .danger {
    color: var(--bad-text);
  }
  .connect {
    max-width: 560px;
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
    color: var(--bad-text);
    background: rgba(240, 113, 103, 0.1);
  }
  .plus {
    color: var(--ok-text);
    background: rgba(76, 195, 138, 0.1);
  }
</style>

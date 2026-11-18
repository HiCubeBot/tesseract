<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import HostForm from '../lib/components/HostForm.svelte';
  import CheckList from '../lib/components/CheckList.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import { api, type Check, type HostInput, type HostSaved, type NodeInfo } from '../lib/api';
  import { emptyHost, upstreamLabel } from '../lib/hosts';
  import { reportApply } from '../lib/nodes';
  import { router } from '../lib/router.svelte';

  let nodes = $state<NodeInfo[]>([]);
  let host = $state<HostInput>(emptyHost());
  let step = $state(1);
  let checks = $state<Check[]>([]);
  let checking = $state(false);
  let preview = $state<unknown>(null);
  let error = $state('');
  let saving = $state(false);
  let showJson = $state(false);

  api.get<NodeInfo[]>('/nodes').then((n) => {
    nodes = n;
    if (!host.node_id && n.length) host.node_id = n[0].id;
  });

  const steps = ['Domain & Ziel', 'Zugriff', 'Prüfen & übertragen'];

  // Prüfungen automatisch, kurz nach der letzten Eingabe
  let timer: ReturnType<typeof setTimeout> | undefined;
  let seq = 0;
  $effect(() => {
    const body = {
      domain: host.domain,
      node_id: host.node_id,
      upstream_host: host.upstream_host,
      upstream_port: Number(host.upstream_port) || null
    };
    clearTimeout(timer);
    if (!body.domain.trim()) {
      checks = [];
      return;
    }
    timer = setTimeout(async () => {
      const mine = ++seq;
      checking = true;
      try {
        const result = await api.post<Check[]>('/hosts/check', body);
        if (mine === seq) checks = result;
      } catch {
        /* Prüfungen sind nur Hinweise */
      } finally {
        if (mine === seq) checking = false;
      }
    }, 500);
  });

  const blocking = $derived(checks.some((c) => c.status === 'bad'));
  const step1Valid = $derived(
    host.domain.trim() !== '' &&
      host.upstream_host.trim() !== '' &&
      Number(host.upstream_port) >= 1 &&
      Number(host.upstream_port) <= 65535 &&
      !!host.node_id &&
      !blocking
  );
  const nodeName = $derived(nodes.find((n) => n.id === host.node_id)?.name ?? '–');
  const domain = $derived(host.domain.trim().toLowerCase().replace(/\.$/, ''));
  const localName = $derived(
    domain === 'localhost' || /\.(localhost|local|internal)$/.test(domain) || /^[\d.]+$|:/.test(domain)
  );

  async function goTo(n: number) {
    error = '';
    if (n === 3) {
      try {
        preview = await api.post('/hosts/preview', { ...host, upstream_port: Number(host.upstream_port) });
      } catch (e) {
        error = e instanceof Error ? e.message : String(e);
        return;
      }
    }
    step = n;
  }

  async function create(draft: boolean) {
    saving = true;
    error = '';
    try {
      const r = await api.post<HostSaved>('/hosts', {
        ...host,
        draft,
        upstream_port: Number(host.upstream_port)
      });
      reportApply(r.apply, r.host.domain);
      router.go(`hosts/${r.host.id}`);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = false;
    }
  }
</script>

<AppShell active="hosts">
  <header class="head">
    <div class="titles">
      <a href="#/hosts" class="crumb">← Proxy-Hosts</a>
      <h1>Host anlegen</h1>
    </div>
    <ol aria-label="Schritte" class="steps">
      {#each steps as label, i (label)}
        {@const n = i + 1}
        <li aria-current={n === step ? 'step' : undefined} class:on={n === step} class:done={n < step}>
          <span class="num">{n < step ? '✓' : n}</span>{label}
        </li>
      {/each}
    </ol>
  </header>

  {#if error}<Alert tone="bad" title="Das hat nicht geklappt" text={error} />{/if}

  {#if step === 1}
    <div class="layout">
      <section class="card main" aria-label="Domain und Ziel">
        <HostForm bind:value={host} {nodes} />
      </section>
      <aside class="card side" aria-label="Automatische Prüfungen">
        <h2>Vorab geprüft</h2>
        <CheckList {checks} busy={checking} />
      </aside>
    </div>
    <footer class="row">
      <Button variant="secondary" label="Abbrechen" href="#/hosts" />
      <span class="spacer"></span>
      <Button label="Weiter: Zugriff" disabled={!step1Valid} onClick={() => goTo(2)} />
    </footer>
  {:else if step === 2}
    <section class="card" aria-labelledby="access-title">
      <h2 id="access-title">Wer darf zugreifen?</h2>
      <div class="access-grid" role="radiogroup" aria-labelledby="access-title">
        <label class="access on">
          <span class="access-head">
            <Icon name="globe" size={18} />
            <strong>Öffentlich</strong>
            <input type="radio" name="access" value="public" bind:group={host.access} />
          </span>
          <span class="muted">Jeder mit der Adresse. Server-Zertifikat von Let's Encrypt, sonst keine Hürde.</span>
        </label>
        <label class="access disabled" aria-disabled="true">
          <span class="access-head">
            <Icon name="lock" size={18} />
            <strong>Nur freigegebene Geräte (mTLS)</strong>
            <input type="radio" name="access" value="mtls" disabled />
          </span>
          <span class="muted">Ohne gültiges Geräte-Zertifikat kommt keine Verbindung zustande. Kommt mit Phase 2.</span>
        </label>
      </div>
    </section>
    <footer class="row">
      <Button variant="secondary" label="Zurück" onClick={() => goTo(1)} />
      <span class="spacer"></span>
      <Button label="Weiter: Prüfen" onClick={() => goTo(3)} />
    </footer>
  {:else}
    <div class="layout">
      <section class="card main" aria-labelledby="sum-title">
        <h2 id="sum-title">Zusammenfassung</h2>
        <dl class="summary">
          <dt>Domain</dt><dd class="mono">{domain}</dd>
          <dt>Ziel</dt><dd class="mono">{upstreamLabel(host)}</dd>
          <dt>Node</dt><dd>{nodeName}</dd>
          <dt>Zugriff</dt><dd>Öffentlich · {localName ? 'lokales Zertifikat von Caddy' : "Let's Encrypt"}</dd>
          <dt>Optionen</dt>
          <dd>
            {[
              host.force_https && 'HTTP → HTTPS',
              host.websockets ? 'WebSockets' : 'keine WebSockets',
              host.compression && 'Kompression'
            ]
              .filter(Boolean)
              .join(' · ')}
          </dd>
        </dl>
        <button type="button" class="link" onclick={() => (showJson = !showJson)} aria-expanded={showJson}>
          {showJson ? 'Caddy-Route ausblenden' : 'Als JSON (Caddy-Route) ansehen'}
        </button>
        {#if showJson}<pre class="code">{JSON.stringify(preview, null, 2)}</pre>{/if}
      </section>
      <aside class="card side" aria-label="Prüfungen">
        <h2>Prüfungen</h2>
        <CheckList {checks} busy={checking} />
        <p class="muted small">Wird an <strong>{nodeName}</strong> übertragen.</p>
      </aside>
    </div>
    <footer class="row">
      <Button variant="secondary" label="Zurück" onClick={() => goTo(2)} />
      <span class="spacer"></span>
      <Button variant="secondary" label="Als Entwurf speichern" disabled={saving || blocking} onClick={() => create(true)} />
      <Button label={saving ? 'Überträgt …' : 'Anlegen & übertragen'} disabled={saving || blocking} onClick={() => create(false)} />
    </footer>
  {/if}
</AppShell>

<style>
  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }
  .titles {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .crumb {
    font-size: 13px;
    font-weight: 500;
    text-decoration: none;
  }
  h1 {
    margin: 0;
    font-size: 26px;
    letter-spacing: -0.02em;
  }
  .steps {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .steps li {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 36px;
    padding: 0 14px 0 6px;
    border-radius: var(--radius-pill);
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted);
  }
  .steps li.on {
    background: var(--surface-raised);
    color: var(--text);
  }
  .num {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 700;
    border: 1px solid var(--border-dashed);
  }
  .on .num {
    background: var(--text);
    color: var(--bg);
    border-color: var(--text);
  }
  .done .num {
    background: rgba(76, 195, 138, 0.18);
    color: var(--ok-text);
    border-color: transparent;
  }
  .layout {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    align-items: flex-start;
  }
  .main {
    flex: 999 1 560px;
    padding: 22px 24px;
  }
  .side {
    flex: 1 1 320px;
  }
  .access-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 12px;
  }
  .access {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 16px;
    border-radius: var(--radius-md);
    background: var(--bg);
    border: 1px solid var(--border-input);
    cursor: pointer;
    font-size: 14px;
    line-height: 1.5;
  }
  .access.on {
    border-color: var(--accent);
    background: rgba(139, 124, 246, 0.1);
  }
  .access.disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
  .access-head {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .access-head strong {
    flex: 1;
  }
  .access input {
    margin: 0;
    accent-color: var(--accent);
  }
  .summary {
    margin: 0;
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 10px 20px;
  }
  dt {
    color: var(--text-muted);
  }
  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
  .link {
    align-self: flex-start;
    padding: 0;
    border: none;
    background: none;
    color: var(--accent-text);
    font: inherit;
    font-size: 13px;
    cursor: pointer;
  }
  .small {
    font-size: 13px;
    margin: 0;
  }
</style>

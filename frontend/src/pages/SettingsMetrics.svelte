<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SettingsTabs from '../lib/components/SettingsTabs.svelte';
  import SegmentedControl from '../lib/components/SegmentedControl.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import ChipInput from '../lib/components/ChipInput.svelte';
  import Toggle from '../lib/components/Toggle.svelte';
  import { api, formatAgo, type IpList } from '../lib/api';
  import { toasts } from '../lib/toast.svelte';

  interface Observability {
    logs_days: number;
    logs_ready: boolean;
    geoip: boolean;
    metrics_enabled: boolean;
    metrics_auth: 'token' | 'mtls' | 'ip';
    metrics_token_set: boolean;
    metrics_networks: string[];
    metrics_list_ids: number[];
    metrics_caddy: boolean;
    metrics_url: string;
    last_scrape: string | null;
    catalog: { name: string; type: string; help: string }[];
  }

  const AUTH = ['token', 'mtls', 'ip'] as const;
  let cfg = $state<Observability | null>(null);
  let lists = $state<IpList[]>([]);
  let auth = $state(0);
  let token = $state('');
  let error = $state('');
  let saving = $state(false);

  async function load() {
    try {
      [cfg, lists] = await Promise.all([api.get<Observability>('/settings/observability'), api.get<IpList[]>('/ip-lists')]);
      auth = AUTH.indexOf(cfg.metrics_auth);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  async function save() {
    if (!cfg) return;
    saving = true;
    try {
      cfg = await api.put<Observability>('/settings/observability', {
        logs_days: Number(cfg.logs_days),
        metrics_enabled: cfg.metrics_enabled,
        metrics_auth: AUTH[auth],
        metrics_networks: cfg.metrics_networks,
        metrics_list_ids: cfg.metrics_list_ids,
        metrics_caddy: cfg.metrics_caddy
      });
      toasts.show('ok', 'Gespeichert.');
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      saving = false;
    }
  }

  async function newToken() {
    try {
      token = (await api.post<{ token: string }>('/settings/observability/token')).token;
      if (cfg) cfg.metrics_token_set = true;
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    }
  }

  function toggleList(id: number) {
    if (!cfg) return;
    cfg.metrics_list_ids = cfg.metrics_list_ids.includes(id)
      ? cfg.metrics_list_ids.filter((x) => x !== id)
      : [...cfg.metrics_list_ids, id];
  }

  function copy(text: string) {
    navigator.clipboard?.writeText(text).then(() => toasts.show('ok', 'Kopiert.'));
  }

  const target = $derived(cfg ? new URL(cfg.metrics_url) : null);
  const snippet = $derived(
    cfg && target
      ? `scrape_configs:
  - job_name: tesseract
    scheme: ${target.protocol.replace(':', '')}
    metrics_path: /metrics
    static_configs:
      - targets: ['${target.host}']${
        AUTH[auth] === 'token'
          ? `
    authorization:
      type: Bearer
      credentials: ${token || '<Token>'}`
          : AUTH[auth] === 'mtls'
            ? `
    tls_config:
      cert_file: /etc/prometheus/admin-geraet.crt
      key_file: /etc/prometheus/admin-geraet.key`
            : ''
      }`
      : ''
  );
</script>

<AppShell active="settings">
  <PageHeader
    title="Einstellungen"
    subtitle="Prometheus-Metriken für Controller und alle Nodes – an einer Stelle abrufbar."
    primaryLabel={saving ? 'Speichert …' : 'Speichern'}
    primaryIcon="check"
    onPrimary={save}
    secondaryLabel="Grafana-Dashboard (JSON)"
    secondaryHref="/api/settings/observability/grafana.json"
  />
  <SettingsTabs current="#/settings-metrics" />

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if cfg}
    <section class="card" aria-labelledby="ep-title">
      <div class="row">
        <h2 id="ep-title">Endpunkt</h2>
        <span class="spacer"></span>
        <span class="muted small">{cfg.last_scrape ? `abgefragt ${formatAgo(cfg.last_scrape)}` : 'noch nicht abgefragt'}</span>
      </div>
      <Toggle label="Metriken anbieten" description={cfg.metrics_url} bind:checked={cfg.metrics_enabled} />
      <div class="field-block">
        <span class="label">Schutz – wer die Metriken abrufen darf</span>
        <SegmentedControl groupLabel="Schutz" options={['Bearer-Token', 'Admin-Gerätezertifikat (mTLS)', 'Nur IP-Liste']} bind:selected={auth} />
      </div>
      {#if AUTH[auth] === 'token'}
        <div class="row">
          <span class="small">Token: {cfg.metrics_token_set ? 'gesetzt' : 'noch keins'}</span>
          <Button variant="secondary" size="sm" icon="refresh" label={cfg.metrics_token_set ? 'Neu erzeugen' : 'Erzeugen'} onClick={newToken} />
        </div>
        {#if token}
          <Alert tone="warn" title="Token jetzt kopieren" text="Es wird nur dieses eine Mal angezeigt. Ein neues Token macht das alte ungültig." />
          <div class="row"><code class="token">{token}</code><Button variant="ghost" size="sm" icon="clipboard" label="Kopieren" onClick={() => copy(token)} /></div>
        {/if}
      {:else if AUTH[auth] === 'mtls'}
        <p class="muted small">Prometheus meldet sich mit dem Zertifikat eines Admin-Geräts (Gruppe „Admin“). Am besten ein eigenes Gerät „prometheus“ dafür ausstellen.</p>
      {:else}
        <ChipInput bind:values={cfg.metrics_networks} label="Netz hinzufügen" placeholder="192.168.178.0/24" />
        {#if lists.length}
          <div class="row">
            {#each lists as l (l.id)}
              <label class="check"><input type="checkbox" checked={cfg.metrics_list_ids.includes(l.id)} onchange={() => toggleList(l.id)} /> Liste „{l.name}“</label>
            {/each}
          </div>
        {/if}
      {/if}
      <Toggle
        label="Caddy-Metriken der Nodes einsammeln"
        description="Der Controller fragt den lokalen Caddy, die Agents liefern ihre mit – jeweils mit Label node."
        bind:checked={cfg.metrics_caddy}
      />
    </section>

    <section class="card" aria-labelledby="prom-title">
      <div class="row">
        <h2 id="prom-title">Für prometheus.yml</h2>
        <span class="spacer"></span>
        <Button variant="ghost" size="sm" icon="clipboard" label="Kopieren" onClick={() => copy(snippet)} />
      </div>
      <pre class="code">{snippet}</pre>
    </section>

    <section class="card" aria-labelledby="logs-title">
      <h2 id="logs-title">Logs</h2>
      <label class="field days">
        <span class="label">Aufbewahrung in Tagen</span>
        <input class="input" type="number" min="1" max="365" bind:value={cfg.logs_days} />
      </label>
      <p class="muted small">
        Zugriffs-Log vom lokalen Caddy: {cfg.logs_ready ? 'wird gelesen' : 'nicht eingerichtet (TESSERACT_CADDY_ACCESS_LOG und TESSERACT_ACCESS_LOG_PATH)'} ·
        GeoIP: {cfg.geoip ? 'Datenbank geladen' : 'keine Datenbank (TESSERACT_GEOIP_DB)'}. Statistik reicht so weit zurück wie die Logs.
      </p>
    </section>

    <section class="card" aria-labelledby="cat-title">
      <h2 id="cat-title">Verfügbare Metriken</h2>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th scope="col">Name</th><th scope="col">Typ</th><th scope="col">Bedeutung</th></tr></thead>
          <tbody>
            {#each cfg.catalog as m (m.name)}
              <tr><td class="mono small">{m.name}</td><td class="small">{m.type}</td><td class="small">{m.help}</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>
  {/if}
</AppShell>

<style>
  .small {
    font-size: 13px;
    margin: 0;
  }
  .label {
    font-size: 13px;
    color: var(--text-muted);
  }
  .field-block {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .token {
    font-family: var(--font-mono);
    font-size: 12px;
    padding: 8px 10px;
    border-radius: var(--radius);
    background: var(--bg-sunken);
    overflow-wrap: anywhere;
  }
  .days {
    max-width: 220px;
    flex-direction: column;
    gap: 6px;
  }
</style>

<script lang="ts">
  import { t, tApi } from '../lib/i18n';
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
    loki_url: string;
    loki_tenant: string;
    loki_kind: 'loki' | 'victorialogs';
    logs_external: boolean;
    loki: { queued: number; pushed: number; dropped: number; last_push_at: string | null; last_error: string | null };
    logs_ready: boolean;
    geoip: boolean;
    geoip_auto: {
      auto: string | null;
      updated_at: string | null;
      file_month: string | null;
      error: string | null;
      attribution: string | null;
    };
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
        loki_url: cfg.loki_url,
        loki_tenant: cfg.loki_tenant,
        loki_kind: cfg.loki_kind,
        logs_external: cfg.logs_external && !!cfg.loki_url,
        metrics_enabled: cfg.metrics_enabled,
        metrics_auth: AUTH[auth],
        metrics_networks: cfg.metrics_networks,
        metrics_list_ids: cfg.metrics_list_ids,
        metrics_caddy: cfg.metrics_caddy
      });
      toasts.show('ok', t('Gespeichert.'));
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      saving = false;
    }
  }

  let testing = $state(false);
  let geoUpdating = $state(false);

  async function updateGeo() {
    geoUpdating = true;
    try {
      await api.post('/settings/observability/geoip-update');
      toasts.show('ok', t('GeoIP-Datenbank aktualisiert.'));
      await load();
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      geoUpdating = false;
    }
  }
  const storeName = $derived(cfg?.loki_kind === 'victorialogs' ? t('VictoriaLogs') : t('Loki'));
  async function testLoki() {
    if (!cfg?.loki_url) return;
    testing = true;
    try {
      const r = await api.post<{ ok: boolean; error: string | null }>('/settings/observability/loki-test', {
        loki_url: cfg.loki_url,
        loki_tenant: cfg.loki_tenant,
        loki_kind: cfg.loki_kind
      });
      if (r.ok) toasts.show('ok', t('{0} hat den Test-Eintrag angenommen.', storeName));
      else toasts.show('bad', `${storeName}: ${r.error}`, 10000);
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      testing = false;
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
    navigator.clipboard?.writeText(text).then(() => toasts.show('ok', t('Kopiert.')));
  }

  const target = $derived(cfg ? new URL(cfg.metrics_url) : null);
  const snippet = $derived(
    cfg && target
      ? t('scrape_configs:\n  - job_name: tesseract\n    scheme: {0}\n    metrics_path: /metrics\n    static_configs:\n      - targets: [\'{1}\']{2}', target.protocol.replace(':', ''), target.host, AUTH[auth] === 'token'
          ? t('\n    authorization:\n      type: Bearer\n      credentials: {0}', token || '<Token>')
          : AUTH[auth] === 'mtls'
            ? t('\n    tls_config:\n      cert_file: /etc/prometheus/admin-geraet.crt\n      key_file: /etc/prometheus/admin-geraet.key')
            : '')
      : ''
  );
</script>

<AppShell active="settings">
  <PageHeader
    title={t('Einstellungen')}
    subtitle={t('Prometheus-Metriken für Controller und alle Nodes – an einer Stelle abrufbar.')}
    primaryLabel={saving ? t('Speichert …') : t('Speichern')}
    primaryIcon="check"
    onPrimary={save}
    secondaryLabel={t('Grafana-Dashboard (JSON)')}
    secondaryHref="/api/settings/observability/grafana.json"
  />
  <SettingsTabs current="#/settings-metrics" />

  {#if error}<Alert tone="bad" title={t('Fehler')} text={error} />{/if}

  {#if cfg}
    <section class="card" aria-labelledby="ep-title">
      <div class="row">
        <h2 id="ep-title">{t('Endpunkt')}</h2>
        <span class="spacer"></span>
        <span class="muted small">{cfg.last_scrape ? `abgefragt ${formatAgo(cfg.last_scrape)}` : t('noch nicht abgefragt')}</span>
      </div>
      <Toggle label={t('Metriken anbieten')} description={cfg.metrics_url} bind:checked={cfg.metrics_enabled} />
      <div class="field-block">
        <span class="label">{t('Schutz – wer die Metriken abrufen darf')}</span>
        <SegmentedControl groupLabel={t('Schutz')} options={['Bearer-Token', t('Admin-Gerätezertifikat (mTLS)'), t('Nur IP-Liste')]} bind:selected={auth} />
      </div>
      {#if AUTH[auth] === 'token'}
        <div class="row">
          <span class="small">{t('Token: {0}', cfg.metrics_token_set ? 'gesetzt' : t('noch keins'))}</span>
          <Button variant="secondary" size="sm" icon="refresh" label={cfg.metrics_token_set ? t('Neu erzeugen') : t('Erzeugen')} onClick={newToken} />
        </div>
        {#if token}
          <Alert tone="warn" title={t('Token jetzt kopieren')} text={t('Es wird nur dieses eine Mal angezeigt. Ein neues Token macht das alte ungültig.')} />
          <div class="row"><code class="token">{token}</code><Button variant="ghost" size="sm" icon="clipboard" label={t('Kopieren')} onClick={() => copy(token)} /></div>
        {/if}
      {:else if AUTH[auth] === 'mtls'}
        <p class="muted small">{t('Prometheus meldet sich mit dem Zertifikat eines Admin-Geräts (Gruppe „Admin“). Am besten ein eigenes Gerät „prometheus“ dafür ausstellen.')}</p>
      {:else}
        <ChipInput bind:values={cfg.metrics_networks} label={t('Netz hinzufügen')} placeholder="192.168.178.0/24" />
        {#if lists.length}
          <div class="row">
            {#each lists as l (l.id)}
              <label class="check"><input type="checkbox" checked={cfg.metrics_list_ids.includes(l.id)} onchange={() => toggleList(l.id)} /> {t('Liste „{0}“', l.name)}</label>
            {/each}
          </div>
        {/if}
      {/if}
      <Toggle
        label={t('Caddy-Metriken der Nodes einsammeln')}
        description={t('Der Controller fragt den lokalen Caddy, die Agents liefern ihre mit – jeweils mit Label node.')}
        bind:checked={cfg.metrics_caddy}
      />
    </section>

    <section class="card" aria-labelledby="prom-title">
      <div class="row">
        <h2 id="prom-title">{t('Für prometheus.yml')}</h2>
        <span class="spacer"></span>
        <Button variant="ghost" size="sm" icon="clipboard" label={t('Kopieren')} onClick={() => copy(snippet)} />
      </div>
      <pre class="code">{snippet}</pre>
    </section>

    <section class="card" aria-labelledby="logs-title">
      <h2 id="logs-title">{t('Logs')}</h2>
      <label class="field days">
        <span class="label">{t('Aufbewahrung in Tagen')}</span>
        <input class="input" type="number" min="1" max="365" bind:value={cfg.logs_days} />
      </label>
      <p class="muted small">
        {t('Zugriffs-Log vom lokalen Caddy: {0} · Statistik reicht so weit zurück wie die Logs.', cfg.logs_ready ? t('wird gelesen') : t('nicht eingerichtet (TESSERACT_CADDY_ACCESS_LOG und TESSERACT_ACCESS_LOG_PATH)'))}
      </p>
      <div class="row">
        <span class="muted small">
          {t('GeoIP:')}
          {#if cfg.geoip_auto.auto}
            {t('automatisch von DB-IP{0}{1}', cfg.geoip_auto.file_month ? t(' · Stand {0}', cfg.geoip_auto.file_month) : '', cfg.geoip_auto.updated_at
              ? t(' · geholt {0}', formatAgo(cfg.geoip_auto.updated_at))
              : t(' · noch nicht geholt'))}
          {:else if cfg.geoip}
            {t('Datenbank aus TESSERACT_GEOIP_DB geladen')}
          {:else}
            {t('keine Datenbank – TESSERACT_GEOIP_AUTO=dbip (automatisch) oder TESSERACT_GEOIP_DB (Datei) setzen')}
          {/if}
        </span>
        {#if cfg.geoip_auto.auto}
          <Button variant="secondary" size="sm" icon="refresh" label={geoUpdating ? t('Lädt …') : t('Jetzt aktualisieren')} disabled={geoUpdating} onClick={updateGeo} />
        {/if}
      </div>
      {#if cfg.geoip_auto.error}<p class="field-error">{t('Letzter Download fehlgeschlagen: {0}', cfg.geoip_auto.error)}</p>{/if}
    </section>

    <section class="card" aria-labelledby="loki-title">
      <div class="row">
        <h2 id="loki-title">{t('Log-Speicher (Loki / VictoriaLogs)')}</h2>
        <span class="spacer"></span>
        {#if cfg.loki_url}
          <span class="muted small">
            {cfg.loki.last_error
              ? t('Fehler: {0}', cfg.loki.last_error)
              : cfg.loki.last_push_at
                ? t('zuletzt gesendet {0}', formatAgo(cfg.loki.last_push_at))
                : t('noch nichts gesendet')}
          </span>
        {/if}
      </div>
      {#if cfg.loki_kind === 'victorialogs'}
        <p class="muted small">
          {t('Zusätzlicher Speicher für lange Aufbewahrung: jeder neue Eintrag geht auch an VictoriaLogs und lässt sich mit LogsQL auswerten, z. B.')} <code>{'{job="tesseract", reason="waf"}'} status:&gt;=400</code>{t('. Die Log-Ansicht und die Statistik hier nutzen weiter die eigene Datenbank. Im Compose-Stack:')} <code>docker compose --profile victorialogs up -d</code> {t('und')}
          <code>http://victorialogs:9428</code>.
        </p>
      {:else}
        <p class="muted small">
          {t('Zusätzlicher Speicher für lange Aufbewahrung: jeder neue Eintrag geht auch an Loki und lässt sich in Grafana mit LogQL auswerten, z. B.')} <code>{'{job="tesseract", reason="waf"}'} | json</code>{t('. Die Log-Ansicht und die Statistik hier nutzen weiter die eigene Datenbank. Im Compose-Stack:')} <code>docker compose --profile loki up -d</code> {t('und')} <code>http://loki:3100</code>.
        </p>
      {/if}
      <div class="loki-fields">
        <label class="field">
          <span class="label">{t('Art')}</span>
          <select class="input" bind:value={cfg.loki_kind}>
            <option value="loki">{t('Loki')}</option>
            <option value="victorialogs">{t('VictoriaLogs')}</option>
          </select>
        </label>
        <label class="field">
          <span class="label">{t('URL (leer = aus)')}</span>
          <input class="input" type="url" placeholder={cfg.loki_kind === 'victorialogs' ? 'http://victorialogs:9428' : 'http://loki:3100'} bind:value={cfg.loki_url} />
        </label>
        <label class="field">
          <span class="label">{cfg.loki_kind === 'victorialogs' ? t('Mandant (AccountID[:ProjectID], optional)') : t('Mandant (X-Scope-OrgID, optional)')}</span>
          <input class="input" type="text" bind:value={cfg.loki_tenant} />
        </label>
      </div>
      <Toggle
        label={t('Log-Ansicht und Statistik aus {0} lesen', storeName)}
        description={t('Suche, Live-Ansicht und Statistik fragen {0} statt der eigenen Datenbank – so weit zurück, wie {1} aufbewahrt. Die eigene Datenbank sammelt weiter (für Auto-Sperre und Benachrichtigungen).', storeName, storeName)}
        bind:checked={cfg.logs_external}
      />
      {#if cfg.logs_external && !cfg.loki_url}<p class="field-error">{t('Erst die URL eintragen.')}</p>{/if}
      <div class="row">
        <Button variant="secondary" size="sm" icon="refresh" label={testing ? t('Prüft …') : t('Verbindung testen')} onClick={testLoki} disabled={!cfg.loki_url || testing} />
        {#if cfg.loki_url}
          <span class="muted small">
            {t('{0} gesendet · {1} im Puffer{2}', cfg.loki.pushed, cfg.loki.queued, cfg.loki.dropped ? t(' · {0} verworfen (Puffer voll)', cfg.loki.dropped) : '')}
          </span>
        {/if}
      </div>
    </section>

    <section class="card" aria-labelledby="cat-title">
      <h2 id="cat-title">{t('Verfügbare Metriken')}</h2>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th scope="col">{t('Name')}</th><th scope="col">{t('Typ')}</th><th scope="col">{t('Bedeutung')}</th></tr></thead>
          <tbody>
            {#each cfg.catalog as m (m.name)}
              <tr><td class="mono small">{m.name}</td><td class="small">{tApi(m.type)}</td><td class="small">{tApi(m.help)}</td></tr>
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
  .loki-fields {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
  }
  .loki-fields .field {
    flex-direction: column;
    gap: 6px;
  }
  .days {
    max-width: 220px;
    flex-direction: column;
    gap: 6px;
  }
</style>

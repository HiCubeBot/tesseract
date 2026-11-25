<script lang="ts">
  import { t } from '../i18n';
  // Einstellungen › Integrationen: Hosts aus Docker-Labels
  import Button from './Button.svelte';
  import Toggle from './Toggle.svelte';
  import { api, formatDate } from '../api';
  import { toasts } from '../toast.svelte';

  interface NodeStatus {
    node: string;
    at: string;
    containers: number;
    created?: string[];
    updated?: string[];
    disabled?: string[];
    enabled?: string[];
    errors: { container: string; error: string }[];
  }
  interface DockerStatus {
    enabled: boolean;
    auto_activate: boolean;
    local: boolean;
    nodes: NodeStatus[];
    hosts: { id: number; domain: string; node: string; container: string; draft: boolean; enabled: boolean }[];
  }

  let st = $state<DockerStatus | null>(null);
  let saving = $state(false);
  let syncing = $state(false);
  let showLabels = $state(false);

  async function load() {
    try {
      st = await api.get<DockerStatus>('/settings/docker');
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    }
  }
  load();

  async function save() {
    if (!st) return;
    saving = true;
    try {
      await api.put('/settings/general', { docker_enabled: st.enabled, docker_auto_activate: st.auto_activate });
      toasts.show('ok', t('Gespeichert.'));
      await load();
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      saving = false;
    }
  }

  async function syncNow() {
    syncing = true;
    try {
      const r = await api.post<{ created: string[]; updated: string[]; errors: unknown[] }>('/settings/docker/sync');
      toasts.show(
        r.errors.length ? 'warn' : 'ok',
        t('Abgeglichen: {0} neu, {1} geändert{2}.', r.created.length, r.updated.length, r.errors.length ? t(', {0} Fehler', r.errors.length) : '')
      );
      await load();
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e), 10000);
    } finally {
      syncing = false;
    }
  }

  const EXAMPLE = t('labels:\n  tesseract.domain: "musik.beispiel.de"   # Pflicht\n  tesseract.port: "4533"                  # Pflicht, außer genau ein Port\n  tesseract.scheme: "http"                # http | https\n  tesseract.upstream: "navidrome"         # Standard: Name des Containers\n  tesseract.access: "mtls"                # public | mtls\n  tesseract.internal: "true"              # nur aus internen Netzen\n  tesseract.grants: "Familie, Ben"        # vorhandene Gruppen/Personen\n  tesseract.waf: "block"                  # off | detect | block\n  tesseract.tls: "dns"                    # http | dns\n  tesseract.enable: "false"               # Container überspringen');
</script>

<section class="card" aria-labelledby="docker-title">
  <h2 id="docker-title">{t('Docker-Labels')}</h2>
  <p class="muted small">
    {t('Proxy-Hosts automatisch aus den Labels von Containern anlegen – ähnlich wie bei Traefik. Den lokalen Node liest der Controller über')}
    <code>TESSERACT_DOCKER_HOST</code> {t('(am besten ein Socket-Proxy mit Nur-Lese-Rechten), Agents melden ihre Container mit')}
    <code>TESSERACT_AGENT_DOCKER_HOST</code>.
  </p>
  {#if st}
    <Toggle label={t('Hosts aus Docker-Labels')} description={t('Container mit tesseract.domain werden zu Hosts; gestoppte Container schalten ihren Host ab')} bind:checked={st.enabled} />
    <Toggle
      label={t('Neue Hosts direkt übertragen')}
      description={t('Aus: neue Hosts landen als Entwurf und gehen erst nach deiner Freigabe an Caddy (empfohlen)')}
      bind:checked={st.auto_activate}
    />
    <div class="row">
      <Button label={saving ? t('Speichert …') : t('Speichern')} disabled={saving} onClick={save} />
      <Button
        variant="secondary"
        icon="refresh"
        label={syncing ? t('Gleicht ab …') : t('Lokal jetzt abgleichen')}
        disabled={syncing || !st.enabled || !st.local}
        onClick={syncNow}
      />
      {#if !st.local}<span class="muted small">{t('Lokal: TESSERACT_DOCKER_HOST nicht gesetzt')}</span>{/if}
    </div>

    {#if st.nodes.length}
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th scope="col">{t('Node')}</th><th scope="col">{t('Zuletzt')}</th><th scope="col">{t('Container')}</th><th scope="col">{t('Hinweise')}</th></tr></thead>
          <tbody>
            {#each st.nodes as n (n.node)}
              <tr>
                <td class="mono">{n.node}</td>
                <td class="small">{formatDate(n.at)}</td>
                <td>{n.containers}</td>
                <td class="small">
                  {#each n.errors as e, i (i)}<div class="err"><span class="mono">{e.container}</span>: {e.error}</div>{:else}<span class="muted">{t('ok')}</span>{/each}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    {#if st.hosts.length}
      <div class="field">
        {t('Hosts aus Labels')}
        <ul class="hosts">
          {#each st.hosts as h (h.id)}
            <li>
              <a class="mono" href={`#/hosts/${h.id}`}>{h.domain}</a>
              <span class="muted small">{h.node} · {h.container}{h.draft ? t(' · Entwurf') : h.enabled ? '' : t(' · abgeschaltet')}</span>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    <button type="button" class="link" aria-expanded={showLabels} onclick={() => (showLabels = !showLabels)}>
      {showLabels ? t('Labels ausblenden') : t('Welche Labels gibt es?')}
    </button>
    {#if showLabels}
      <pre class="code">{EXAMPLE}</pre>
      <p class="muted small">
        {t('Ändern sich die Labels, gelten sie (neue Version, Akteur „docker“). Felder ohne Label stellst du in der Oberfläche ein. Domains, die schon ein manuell angelegter Host nutzt, werden nicht übernommen. Freigaben gehen nur an Gruppen und Personen, die es schon gibt.')}
      </p>
    {/if}
  {/if}
</section>

<style>
  .small {
    font-size: 13px;
    margin: 0;
  }
  .err {
    color: var(--warn-text);
  }
  .hosts {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 6px;
    color: var(--text);
  }
  .hosts li {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 10px;
    align-items: baseline;
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
  code {
    font-family: var(--font-mono);
    color: var(--text-soft);
  }
</style>

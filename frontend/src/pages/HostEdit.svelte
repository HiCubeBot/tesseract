<script lang="ts">
  // Host bearbeiten – volle Seite mit Tabs „Allgemein“ und „Zugriff“
  // (Sicherheit und Verlauf sind eigene Seiten mit demselben Kopf)
  import AppShell from '../lib/components/AppShell.svelte';
  import HostHeader from '../lib/components/HostHeader.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import HostForm from '../lib/components/HostForm.svelte';
  import AccessForm from '../lib/components/AccessForm.svelte';
  import CheckList from '../lib/components/CheckList.svelte';
  import {
    api,
    formatDate,
    type CAStatus,
    type Check,
    type CustomCert,
    type DnsZone,
    type GeneralSettings,
    type Group,
    type Host,
    type HostInput,
    type HostSaved,
    type NodeInfo,
    type Person
  } from '../lib/api';
  import { toInput } from '../lib/hosts';
  import { reportApply } from '../lib/nodes';
  import { router } from '../lib/router.svelte';
  import { toasts } from '../lib/toast.svelte';

  let { params = {} }: { params?: Record<string, string> } = $props();
  const hostId = $derived(Number(params.id));
  const tab = $derived(router.path.endsWith('/access') ? 'access' : 'general');

  let host = $state<Host | null>(null);
  let form = $state<HostInput | null>(null);
  let nodes = $state<NodeInfo[]>([]);
  let groups = $state<Group[]>([]);
  let persons = $state<Person[]>([]);
  let customCerts = $state<CustomCert[]>([]);
  let caConfigured = $state(false);
  let dnsAvailable = $state(false);
  let internalAvailable = $state(false);
  let wildcards = $state<string[]>([]);
  let error = $state('');
  let saving = $state(false);
  let confirmDelete = $state(false);

  async function load() {
    try {
      let ca: CAStatus;
      let general: GeneralSettings;
      [host, nodes, groups, persons, ca, general] = await Promise.all([
        api.get<Host>(`/hosts/${hostId}`),
        api.get<NodeInfo[]>('/nodes'),
        api.get<Group[]>('/groups'),
        api.get<Person[]>('/persons'),
        api.get<CAStatus>('/ca'),
        api.get<GeneralSettings>('/settings/general')
      ]);
      form = toInput(host);
      caConfigured = ca.configured;
      dnsAvailable = general.cloudflare_token_set;
      wildcards = general.wildcard_certs;
      internalAvailable = general.internal_networks.length > 0 || general.internal_list_ids.length > 0;
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();
  api.get<CustomCert[]>('/custom-certs').then((c) => (customCerts = c), () => {});
  let dnsZones = $state<DnsZone[]>([]);
  api.get<{ zones: DnsZone[]; token_set: boolean }>('/settings/dns-zones').then(
    (r) => (dnsZones = r.token_set ? r.zones : []),
    () => {}
  );

  const dirty = $derived(!!host && !!form && JSON.stringify(form) !== JSON.stringify(toInput(host)));

  // Vorab-Prüfungen wie beim Anlegen (die eigene Domain zählt nicht als belegt)
  let checks = $state<Check[]>([]);
  let checking = $state(false);
  let timer: ReturnType<typeof setTimeout> | undefined;
  let seq = 0;
  $effect(() => {
    if (!form || tab !== 'general') return;
    const body = {
      domain: form.domain,
      node_id: form.node_id,
      upstream_host: form.upstream_host,
      upstream_port: Number(form.upstream_port) || null,
      exclude_id: hostId,
      dns_type: form.dns_type,
      dns_target: form.dns_target
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

  async function save(activate = false) {
    if (!form || !host) return;
    saving = true;
    error = '';
    try {
      const body = { ...form, draft: activate ? false : form.draft, upstream_port: Number(form.upstream_port) };
      const r = await api.put<HostSaved>(`/hosts/${host.id}`, body);
      reportApply(r.apply, r.host.domain, r.dns);
      host = r.host;
      form = toInput(r.host);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = false;
    }
  }

  async function remove() {
    if (!host) return;
    const domain = host.domain;
    try {
      const r = await api.del<{ ok: boolean; error: string | null }>(`/hosts/${host.id}`);
      if (r.ok) toasts.show('ok', `${domain} gelöscht und übertragen.`);
      else toasts.show('warn', `${domain} gelöscht, aber nicht übertragen: ${r.error}`, 12000);
      router.go('hosts');
    } catch (e) {
      toasts.show('bad', e instanceof Error ? e.message : String(e));
    } finally {
      confirmDelete = false;
    }
  }

  // Aktiv-Schalter im Kopf: nur „enabled“ übernehmen, andere Eingaben bleiben
  function enabledChanged(updated: Host) {
    host = updated;
    if (form) form.enabled = updated.enabled;
  }
</script>

<AppShell active="hosts">
  <HostHeader {hostId} {host} {tab} {dirty} onChange={enabledChanged} />

  {#if error}<Alert tone="bad" title="Das hat nicht geklappt" text={error} />{/if}

  {#if host && form}
    {#if host.draft}
      <Alert tone="warn" title="Entwurf" text="Dieser Host ist gespeichert, aber noch nicht an Caddy übertragen." />
    {/if}
    {#if host.source === 'docker'}
      <Alert
        tone="info"
        title={`Aus Docker-Labels · Container ${host.source_ref?.split(':').slice(1).join(':')}`}
        text={host.source_disabled
          ? 'Der Container läuft nicht – der Host ist deshalb abgeschaltet und wird wieder aktiv, sobald der Container läuft.'
          : 'Ändern sich die Labels des Containers, gelten sie und überschreiben die betroffenen Felder. Felder ohne Label bleiben, wie du sie hier einstellst.'}
      />
    {/if}

    {#if tab === 'general'}
      <div class="layout">
        <section class="card main" aria-label="Domain und Ziel">
          <HostForm bind:value={form} {nodes} {dnsAvailable} {wildcards} {customCerts} {dnsZones} />
        </section>
        <aside class="side">
          <section class="card" aria-labelledby="checks-title">
            <h2 id="checks-title">Prüfungen</h2>
            <CheckList {checks} busy={checking} />
          </section>
          <section class="card" aria-labelledby="meta-title">
            <h2 id="meta-title">Details</h2>
            <dl class="meta">
              <dt>Angelegt</dt><dd>{formatDate(host.created_at)}</dd>
              <dt>Geändert</dt><dd>{formatDate(host.updated_at)}</dd>
              <dt>Version</dt><dd><a href={`#/hosts/${host.id}/history`}>{host.version}</a></dd>
              {#if host.dns_records.length}
                <dt>DNS</dt>
                <dd class="mono">
                  {#each host.dns_records as r (r.id)}<div>{r.type} → {r.content}{r.proxied ? ' (Proxy)' : ''}</div>{/each}
                </dd>
              {/if}
            </dl>
            {#if host.dns_error}
              <p class="field-error">DNS-Eintrag: {host.dns_error}. Erneut speichern versucht es noch einmal.</p>
            {/if}
          </section>
        </aside>
      </div>
    {:else}
      <section class="card" aria-labelledby="access-title">
        <h2 id="access-title">Wer darf zugreifen?</h2>
        <AccessForm bind:value={form} {groups} {persons} {caConfigured} {internalAvailable} />
      </section>
    {/if}

    <footer class="row bar">
      {#if host.draft}
        <Button label={saving ? 'Überträgt …' : 'Anlegen & übertragen'} disabled={saving || blocking} onClick={() => save(true)} />
        <Button variant="secondary" label="Entwurf speichern" disabled={saving || !dirty} onClick={() => save(false)} />
      {:else}
        <Button label={saving ? 'Überträgt …' : 'Speichern & übertragen'} disabled={saving || !dirty || blocking} onClick={() => save(false)} />
      {/if}
      <Button variant="secondary" label="Verwerfen" disabled={saving || !dirty} onClick={() => host && (form = toInput(host))} />
      {#if dirty}<span class="muted small">Ungespeicherte Änderungen</span>{/if}
      <span class="spacer"></span>
      <Button variant="danger" icon="trash" label="Löschen" onClick={() => (confirmDelete = true)} />
    </footer>

    {#if confirmDelete}
      <ConfirmDialog
        title="Host löschen?"
        text={`${host.domain} wird aus Caddy entfernt. Der Verlauf geht verloren. Zum vorübergehenden Abschalten reicht der Schalter „Aktiv“.`}
        word={host.domain}
        confirmLabel="Endgültig löschen"
        onConfirm={remove}
        onCancel={() => (confirmDelete = false)}
      />
    {/if}
  {/if}
</AppShell>

<style>
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
    flex: 1 1 300px;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  .meta {
    margin: 0;
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 8px 16px;
    font-size: 13px;
  }
  dt {
    color: var(--text-muted);
  }
  dd {
    margin: 0;
  }
  .small {
    font-size: 13px;
  }
  /* Speichern bleibt beim Scrollen sichtbar */
  .bar {
    position: sticky;
    bottom: 0;
    padding: 12px 0;
    background: var(--bg);
    border-top: 1px solid var(--border);
    z-index: 5;
  }
</style>

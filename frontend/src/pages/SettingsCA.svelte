<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SettingsTabs from '../lib/components/SettingsTabs.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import IssuedCertificate from '../lib/components/IssuedCertificate.svelte';
  import { api, downloadFile, formatDay, type AuthorityInfo, type CAStatus, type IssuedDevice } from '../lib/api';
  import { toasts } from '../lib/toast.svelte';

  let status = $state<CAStatus | null>(null);
  let error = $state('');

  let pass1 = $state('');
  let pass2 = $state('');
  let creating = $state(false);
  let created = $state<{ root_cert_pem: string; root_key_pem: string } | null>(null);
  let keySaved = $state(false);
  let keyDownloaded = $state(false);

  async function load() {
    try {
      status = await api.get<CAStatus>('/ca');
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  load();

  async function setup(e: SubmitEvent) {
    e.preventDefault();
    error = '';
    if (pass1 !== pass2) {
      error = 'Die Passphrasen stimmen nicht überein.';
      return;
    }
    creating = true;
    try {
      created = await api.post('/ca/setup', { passphrase: pass1 });
      pass1 = pass2 = '';
      toasts.show('ok', 'Zertifizierungsstelle eingerichtet.');
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      creating = false;
    }
  }

  function downloadKey() {
    if (!created) return;
    downloadFile('tesseract-root-ca.key', created.root_key_pem, 'application/x-pem-file');
    keyDownloaded = true;
  }

  function downloadRoot() {
    if (created) downloadFile('tesseract-root-ca.pem', created.root_cert_pem, 'application/x-pem-file');
    else window.location.href = '/api/ca/root.pem';
  }

  // Warnen, wenn die Seite verlassen wird, bevor der Root-Schlüssel gesichert ist
  $effect(() => {
    if (!created || keySaved) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  });

  async function finish() {
    created = null;
    await load();
  }

  const yearsLeft = (a: AuthorityInfo) =>
    Math.max(0, Math.round((new Date(a.not_after).getTime() - Date.now()) / (365.25 * 86400_000) * 10) / 10);

  // ---------- Phase 6: Wechsel des Zwischenzertifikats, Verlängern ----------
  let rootKey = $state('');
  let rootPass = $state('');
  let rotating = $state(false);
  let renewing = $state<number | null>(null);
  let renewed = $state<IssuedDevice | null>(null);

  async function readKey(e: Event) {
    const f = (e.currentTarget as HTMLInputElement).files?.[0];
    if (f) rootKey = await f.text();
  }

  async function rotate(e: Event) {
    e.preventDefault();
    rotating = true;
    try {
      status = await api.post<CAStatus>('/ca/rotate', { root_key_pem: rootKey, passphrase: rootPass });
      rootKey = rootPass = '';
      toasts.show('ok', 'Neues Zwischenzertifikat aktiv. Alte Geräte funktionieren weiter und lassen sich nach und nach verlängern.', 10000);
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err), 10000);
    } finally {
      rotating = false;
    }
  }

  async function renew(id: number) {
    renewing = id;
    try {
      renewed = await api.post<IssuedDevice>(`/devices/${id}/renew`, { days: 365 });
      status = await api.get<CAStatus>('/ca');
    } catch (err) {
      toasts.show('bad', err instanceof Error ? err.message : String(err), 10000);
    } finally {
      renewing = null;
    }
  }
</script>

<AppShell active="settings">
  <PageHeader title="Einstellungen" subtitle="Die eigene CA stellt Geräte-, Admin- und Node-Zertifikate aus." />
  <SettingsTabs current="#/settings-ca" />

  {#if error}<Alert tone="bad" title="Fehler" text={error} />{/if}

  {#if created}
    <section class="card setup done" aria-labelledby="done-title">
      <h2 id="done-title">Root-Schlüssel jetzt sichern</h2>
      <p class="muted">
        Der Root-Schlüssel ist mit deiner Passphrase verschlüsselt. Er wird nur gebraucht, um später ein neues
        Zwischenzertifikat zu signieren – bewahre ihn offline auf (z. B. USB-Stick im Schrank).
        <strong>Tesseract speichert ihn nicht.</strong>
      </p>
      <div class="row">
        <Button icon="download" label="Root-Schlüssel herunterladen" onClick={downloadKey} />
        <Button variant="secondary" icon="download" label="Root-Zertifikat (.pem)" onClick={downloadRoot} />
      </div>
      <label class="check">
        <input type="checkbox" bind:checked={keySaved} disabled={!keyDownloaded} />
        Ich habe den Root-Schlüssel und die Passphrase sicher gespeichert.
      </label>
      <div class="row"><Button label="Fertig" disabled={!keySaved} onClick={finish} /></div>
    </section>
  {:else if status && !status.configured}
    <form class="card setup" onsubmit={setup} aria-labelledby="setup-title">
      <h2 id="setup-title">Zertifizierungsstelle einrichten</h2>
      <ol class="steps muted">
        <li>Tesseract erzeugt eine <strong>Root-CA</strong> (ECDSA P-384, 10 Jahre) und ein <strong>Geräte-Zwischenzertifikat</strong> (3 Jahre).</li>
        <li>Den Root-Schlüssel lädst du einmal herunter – verschlüsselt mit dieser Passphrase. Danach vergisst Tesseract ihn.</li>
        <li>Das Zwischenzertifikat bleibt verschlüsselt auf dem Controller und stellt die Gerätezertifikate aus.</li>
      </ol>
      <div class="grid2">
        <label class="field">
          Passphrase für den Root-Schlüssel (mind. 12 Zeichen)
          <input class="input" type="password" autocomplete="new-password" minlength="12" required bind:value={pass1} />
        </label>
        <label class="field">
          Passphrase wiederholen
          <input class="input" type="password" autocomplete="new-password" minlength="12" required bind:value={pass2} />
        </label>
      </div>
      <div class="row">
        <Button type="submit" label={creating ? 'Erzeugt …' : 'CA erzeugen'} disabled={creating} />
      </div>
    </form>
  {:else if status}
    {#if status.devices_beyond_intermediate > 0 && status.intermediate}
      <Alert
        tone="warn"
        title={`${status.devices_beyond_intermediate} Gerät(e) „unbegrenzt“ gültig`}
        text={`Sie funktionieren nur bis ${formatDay(status.intermediate.not_after)} – solange das Zwischenzertifikat gilt.`}
      />
    {/if}

    <div class="chain" aria-label="Aufbau der CA">
      {#each [status.root, status.intermediate] as a, i (i)}
        {#if a}
          <section class="card">
            <div class="row">
              <span class="ca-icon"><Icon name="lock" size={16} strokeWidth={2} /></span>
              <h2 class="card-title">{a.kind === 'root' ? 'Root-Zertifikat' : 'Geräte-Zwischenzertifikat'}</h2>
              <span class="spacer"></span>
              <StatusPill tone="ok" label="aktiv" />
            </div>
            <dl>
              <dt>Name</dt><dd>{a.subject}</dd>
              <dt>Gültig</dt><dd>{formatDay(a.not_before)} – {formatDay(a.not_after)} · noch {yearsLeft(a)} Jahre</dd>
              <dt>Schlüssel</dt>
              <dd>{a.key_on_controller ? 'verschlüsselt auf dem Controller' : 'offline – nicht auf dem Controller'}</dd>
              <dt>Fingerabdruck</dt><dd class="mono fp">{a.fingerprint}</dd>
            </dl>
          </section>
        {/if}
      {/each}
    </div>

    <section class="card">
      <h2>Ausgestellte Gerätezertifikate</h2>
      <p class="muted">
        {status.devices_total} Geräte · {status.devices_active} aktiv · {status.devices_revoked} gesperrt
        · <a href="#/devices">Geräte ansehen</a>
      </p>
      <div class="row">
        <Button variant="secondary" icon="download" label="Root-Zertifikat herunterladen" onClick={downloadRoot} />
      </div>
    </section>

    {#each status.previous as prev (prev.authority.fingerprint)}
      <section class="card retiring">
        <div class="row">
          <h2 class="card-title">Altes Zwischenzertifikat – noch vertraut</h2>
          <span class="spacer"></span>
          <StatusPill tone="warn" label={`${prev.devices.length} Gerät(e)`} />
        </div>
        <p class="muted small">
          Gültig bis {formatDay(prev.authority.not_after)}. Caddy vertraut ihm, bis alle Geräte unten verlängert sind – danach fällt es weg.
        </p>
        <ul class="devlist">
          {#each prev.devices as d (d.id)}
            <li>
              <span>{d.person} · {d.name}</span>
              <Button variant="secondary" size="sm" label={renewing === d.id ? 'Verlängert …' : 'Verlängern'} disabled={renewing !== null} onClick={() => renew(d.id)} />
            </li>
          {/each}
        </ul>
      </section>
    {/each}

    <form class="card" onsubmit={rotate} aria-labelledby="rot-title">
      <h2 id="rot-title">Wechsel auf ein neues Zwischenzertifikat</h2>
      <p class="muted small">
        Dafür wird der Root-Schlüssel gebraucht, den du bei der Einrichtung gesichert hast (Datei <span class="mono">tesseract-root-key.pem</span>, mit
        Passphrase verschlüsselt). Er wird nur für diesen Vorgang entschlüsselt und nicht gespeichert. Bestehende Geräte funktionieren weiter;
        verlängerte und neue bekommen ihr Zertifikat vom neuen Zwischenzertifikat. Empfohlen spätestens 90 Tage vor Ablauf.
      </p>
      <label class="field col">
        <span class="label">Root-Schlüssel (Datei wählen oder Inhalt einfügen)</span>
        <input class="input" type="file" accept=".pem,.key,.txt" onchange={readKey} />
        <textarea class="input mono keyarea" rows="4" bind:value={rootKey} placeholder="-----BEGIN ENCRYPTED PRIVATE KEY-----"></textarea>
      </label>
      <label class="field col">
        <span class="label">Passphrase des Root-Schlüssels</span>
        <input class="input" type="password" autocomplete="off" bind:value={rootPass} />
      </label>
      <div class="row">
        <Button type="submit" label={rotating ? 'Wechselt …' : 'Wechsel durchführen'} disabled={rotating || !rootKey.trim() || !rootPass} />
      </div>
    </form>
    {#if renewed}<IssuedCertificate issued={renewed} onClose={() => (renewed = null)} />{/if}
  {/if}
</AppShell>

<style>
  .retiring {
    border-color: rgba(229, 164, 67, 0.45);
  }
  .devlist {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .devlist li {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }
  .col {
    flex-direction: column;
    gap: 6px;
  }
  .label {
    font-size: 13px;
    color: var(--text-muted);
  }
  .keyarea {
    font-size: 11px;
    resize: vertical;
  }
  h2 {
    margin: 0;
    font-size: 16px;
  }
  .setup {
    max-width: 760px;
  }
  .done {
    border-color: var(--warn);
  }
  .steps {
    margin: 0;
    padding-left: 20px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    line-height: 1.5;
  }
  .steps strong,
  p strong {
    color: var(--text);
  }
  p {
    margin: 0;
    line-height: 1.55;
  }
  .grid2 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 12px;
  }
  .chain {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 18px;
  }
  .ca-icon {
    width: 30px;
    height: 30px;
    border-radius: var(--radius);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: rgba(139, 124, 246, 0.18);
    color: #c9c1ff;
  }
  dl {
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
    overflow-wrap: anywhere;
  }
  .fp {
    font-size: 11px;
  }
  .small {
    font-size: 12px;
  }
</style>

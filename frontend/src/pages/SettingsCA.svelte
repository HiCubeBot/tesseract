<script lang="ts">
  import AppShell from '../lib/components/AppShell.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SettingsTabs from '../lib/components/SettingsTabs.svelte';
  import Button from '../lib/components/Button.svelte';
  import Alert from '../lib/components/Alert.svelte';
  import StatusPill from '../lib/components/StatusPill.svelte';
  import Icon from '../lib/components/Icon.svelte';
  import { api, downloadFile, formatDay, type AuthorityInfo, type CAStatus } from '../lib/api';
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
      <p class="muted small">Wechsel auf ein neues Zwischenzertifikat folgt mit Phase 6.</p>
    </section>
  {/if}
</AppShell>

<style>
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
